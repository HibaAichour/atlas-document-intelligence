"""Measure whether keeping only the passages close to the best score helps the Writer.

With bge-m3 and RETRIEVAL_MIN_SCORE = 0.44, the scores are close together, so
the 5 passages of the top 5 nearly always pass the threshold. For demo
scenario 1 ("What is the termination notice period?"), Article 4.4 then reaches
the Writer, which presents its 30-day remedy period as a notice period.

The idea measured here: on top of the threshold, keep only the passages whose
score is within a gap of the best one (for example 0.05). Nothing is changed in
the application; the filter is applied inside this script.

Two parts, run separately:
- search only (default, a few seconds): for every question of probe_scores,
  how many passages each gap keeps, and whether the right passage (expected
  file and page) is lost. A gap never changes a refusal by the threshold: when
  the best passage passes the threshold, it is always kept.
- --writer (a few minutes): a few questions in English and French go through
  the real Writer and Critic, once per gap, and each answer is checked against
  what a right answer contains. A gap that keeps the same passages as a
  previous one reuses its answer (temperature 0: same prompt, same answer).

The search goes through the running server (POST /api/search), so Chroma is
only opened by the server. The Writer and the Critic are built here from the
local settings (.env), and call Ollama directly. Nothing is saved.

Usage, from backend/ while the server and Ollama are running:
    python -m scripts.probe_margin
    python -m scripts.probe_margin --writer
    python -m scripts.probe_margin --all-documents     (every indexed document, as in Docker)
    python -m scripts.probe_margin --url http://localhost:8080
"""

import argparse
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass, field

import httpx2

from app.agents.critic import Critic
from app.agents.writer import Writer
from app.core.config import get_settings
from app.core.providers import build_llm_provider
from app.llm.base import LLMError
from app.retrieval.retriever import RetrievedPassage
from scripts.probe_scores import QUESTION_SETS, expected_pages
from scripts.probe_writer_fr import demo_document_ids

# None means "no gap": the threshold alone, as the application does today.
Gap = float | None
SEARCH_GAPS: tuple[Gap, ...] = (None, 0.08, 0.05, 0.03)
WRITER_GAPS: tuple[Gap, ...] = (None, 0.05, 0.03)

# Rounding errors must not drop a passage that sits exactly at the gap.
_TOLERANCE = 1e-9


def gap_label(gap: Gap) -> str:
    return "none" if gap is None else f"{gap:.2f}"


def keep_passages(
    passages: Sequence[RetrievedPassage], min_score: float, gap: Gap
) -> list[RetrievedPassage]:
    """The passages the Writer would receive: above the threshold, then near the best."""
    above = [passage for passage in passages if passage.score >= min_score]
    if gap is None or not above:
        return above
    best = max(passage.score for passage in above)
    return [passage for passage in above if passage.score >= best - gap - _TOLERANCE]


# Part 1: search only.


def classify(
    passages: Sequence[RetrievedPassage],
    filename: str,
    pages: tuple[int, ...],
    min_score: float,
    gap: Gap,
) -> tuple[int, str]:
    """How many passages a gap keeps, and what happens to the question.

    Status, for an answerable question (pages given):
    - "right":   the right passage is among the kept passages;
    - "LOST":    the threshold alone keeps it, but the gap removes it;
    - "missing": the threshold alone already misses it (the gap is not the cause).
    For a question the documents cannot answer (no pages):
    - "refused": nothing is kept, so the application refuses without the LLM;
    - "passed":  passages reach the Writer, which must refuse by itself.
    """
    kept = keep_passages(passages, min_score, gap)
    if not pages:
        return len(kept), "refused" if not kept else "passed"

    def has_right(candidates: Sequence[RetrievedPassage]) -> bool:
        return any(p.filename == filename and p.page_number in pages for p in candidates)

    if has_right(kept):
        return len(kept), "right"
    if has_right(keep_passages(passages, min_score, None)):
        return len(kept), "LOST"
    return len(kept), "missing"


@dataclass(slots=True)
class SearchRow:
    set_name: str
    question: str
    answerable: bool
    results: dict[Gap, tuple[int, str]]  # gap -> (passages kept, status)


def search_summary(rows: Sequence[SearchRow], gaps: Sequence[Gap]) -> list[str]:
    """One line per gap: passages kept on average, right passages kept and lost."""
    answerable = [row for row in rows if row.answerable]
    absent = [row for row in rows if not row.answerable]
    lines = [f"{'gap':<6}{'avg kept':>10}{'right kept':>12}{'LOST':>6}{'missing':>9}"]
    for gap in gaps:
        counts = [row.results[gap][0] for row in answerable]
        statuses = [row.results[gap][1] for row in answerable]
        average = sum(counts) / len(counts) if counts else 0.0
        lines.append(
            f"{gap_label(gap):<6}{average:>10.1f}"
            f"{statuses.count('right'):>7} of {len(answerable):<2}"
            f"{statuses.count('LOST'):>6}{statuses.count('missing'):>9}"
        )
    refused = sum(row.results[gaps[0]][1] == "refused" for row in absent)
    lines.append(
        f"Absent information refused by the threshold: {refused} of {len(absent)} "
        "(the same for every gap)"
    )
    return lines


# Part 2: Writer and Critic.


@dataclass(frozen=True, slots=True)
class WriterCase:
    """A question, what a right answer contains (any of), and what it must not contain.

    expected None: the documents do not hold the answer, a refusal is expected.
    """

    question: str
    language: str
    expected: tuple[str, ...] | None
    forbidden: tuple[str, ...] = ()


WRITER_CASES: list[WriterCase] = [
    # Demo scenario 1: 60 days (4.3); 30 days is the remedy period of 4.4.
    WriterCase(
        "What is the termination notice period?",
        "en",
        ("60 days", "60-day", "60 jours"),
        ("30 days", "30-day", "30 jours"),
    ),
    WriterCase(
        "Quel est le préavis de résiliation ?",
        "fr",
        ("60 days", "60-day", "60 jours"),
        ("30 days", "30-day", "30 jours"),
    ),
    WriterCase("How much was invoiced in Q2 2026?", "en", ("45,370", "45 370")),
    WriterCase(
        "Combien coûte le raccordement de l'entrepôt de Marseille ?", "fr", ("17 100", "17,100")
    ),
    WriterCase("What was the platform availability in May 2026?", "en", ("99.38", "99,38")),
    WriterCase("What caused the outage in May 2026?", "en", ("storage", "stockage")),
    WriterCase("What service credit is due for May 2026?", "en", ("625",)),
    WriterCase("Quel est le montant de l'avoir accordé pour le mois de mai ?", "fr", ("625",)),
    WriterCase(
        "Qui doit mettre en place l'alerte d'expiration des certificats ?", "fr", ("Lefèvre",)
    ),
    WriterCase("What was Orion Freight's revenue in Q2 2026?", "en", None),
    WriterCase("Quel est le chiffre d'affaires d'Orion au deuxième trimestre 2026 ?", "fr", None),
]


@dataclass(slots=True)
class Outcome:
    """What the ask plan would return with these passages."""

    passages: int
    refused: str | None = None  # "threshold", "model" or "error: ..."; None when answered
    answer: str = ""
    sources: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)  # "code (origin)"
    seconds: float = 0.0


def normalize(text: str) -> str:
    """Lower case, one plain space between words (French texts use narrow spaces)."""
    return " ".join(text.replace("\u202f", " ").replace("\xa0", " ").split()).lower()


def judge(case: WriterCase, outcome: Outcome) -> bool:
    """True when the outcome is what a right answer looks like."""
    if case.expected is None:
        return outcome.refused in ("threshold", "model")
    if outcome.refused is not None:
        return False
    answer = normalize(outcome.answer)
    if not any(normalize(text) in answer for text in case.expected):
        return False
    return not any(normalize(text) in answer for text in case.forbidden)


def run_plan(
    writer: Writer, critic: Critic, question: str, passages: Sequence[RetrievedPassage]
) -> Outcome:
    """The writer and critic steps of the ask plan, on the given passages."""
    outcome = Outcome(passages=len(passages))
    if not passages:
        outcome.refused = "threshold"
        return outcome
    start = time.perf_counter()
    try:
        written = writer.write(question, passages)
        if written.refused or written.answer is None:
            outcome.refused = "model"
        else:
            checked = written.answer
            review = critic.review_answer(checked, passages)
            outcome.answer = " ".join(checked.text.split())
            outcome.sources = sorted(
                {f"{c.passage.filename[:24]} p.{c.passage.page_number}" for c in checked.citations}
            )
            outcome.issues = [f"{issue.code} ({issue.origin})" for issue in review.issues]
    except LLMError as error:
        outcome.refused = f"error: {error}"
    outcome.seconds = time.perf_counter() - start
    return outcome


def outcomes_by_gap(
    writer: Writer,
    critic: Critic,
    question: str,
    passages: Sequence[RetrievedPassage],
    min_score: float,
    gaps: Sequence[Gap],
) -> dict[Gap, Outcome]:
    """One outcome per gap; a gap keeping the same passages reuses the answer."""
    by_chunks: dict[tuple[str, ...], Outcome] = {}
    outcomes: dict[Gap, Outcome] = {}
    for gap in gaps:
        kept = keep_passages(passages, min_score, gap)
        key = tuple(passage.chunk_id for passage in kept)
        if key not in by_chunks:
            by_chunks[key] = run_plan(writer, critic, question, kept)
        outcomes[gap] = by_chunks[key]
    return outcomes


def writer_summary(
    results: Sequence[tuple[WriterCase, dict[Gap, Outcome]]], gaps: Sequence[Gap]
) -> list[str]:
    """One line per gap: right answers, Critic issues, model time."""
    lines = [f"{'gap':<6}{'right':>10}{'Critic issues':>15}{'time':>9}"]
    for gap in gaps:
        right = sum(judge(case, outcomes[gap]) for case, outcomes in results)
        issues = sum(len(outcomes[gap].issues) for _, outcomes in results)
        # Reused answers are counted once per gap: the time a real run would take.
        seconds = sum(outcomes[gap].seconds for _, outcomes in results)
        lines.append(
            f"{gap_label(gap):<6}{right:>5} of {len(results):<2}{issues:>15}{seconds:>8.1f}s"
        )
    return lines


# Running against the server.


def search(
    client: httpx2.Client, question: str, top_k: int, document_ids: list[str] | None
) -> list[RetrievedPassage]:
    response = client.post(
        "/api/search", json={"query": question, "top_k": top_k, "document_ids": document_ids}
    )
    response.raise_for_status()
    return [RetrievedPassage(**result) for result in response.json()["results"]]


def run_search_part(
    client: httpx2.Client, top_k: int, document_ids: list[str] | None, min_score: float
) -> None:
    rows: list[SearchRow] = []
    for set_name, (filename, questions) in QUESTION_SETS.items():
        print(f"=== {set_name} ({filename}) ===")
        for question, expected in questions:
            passages = search(client, question, top_k, document_ids)
            pages = expected_pages(expected)
            results = {
                gap: classify(passages, filename, pages, min_score, gap) for gap in SEARCH_GAPS
            }
            rows.append(SearchRow(set_name, question, bool(pages), results))
            scores = " ".join(f"{p.score:.3f}" for p in passages)
            cells = "  ".join(
                f"{gap_label(gap)}={count} {status}" for gap, (count, status) in results.items()
            )
            print(f"{question}\n    scores: {scores}\n    {cells}")
        print()
    print(f"Threshold {min_score:.2f}, top-k {top_k}, {len(rows)} questions")
    for line in search_summary(rows, SEARCH_GAPS):
        print(line)


def run_writer_part(
    client: httpx2.Client, top_k: int, document_ids: list[str] | None, min_score: float
) -> None:
    settings = get_settings()
    llm = build_llm_provider(settings)
    writer = Writer(llm)
    critic = Critic(llm, use_model=settings.critic_use_llm)
    results: list[tuple[WriterCase, dict[Gap, Outcome]]] = []
    for number, case in enumerate(WRITER_CASES, 1):
        passages = search(client, case.question, top_k, document_ids)
        outcomes = outcomes_by_gap(writer, critic, case.question, passages, min_score, WRITER_GAPS)
        results.append((case, outcomes))
        expected = " / ".join(case.expected) if case.expected else "refusal"
        forbidden = f" ; not: {' / '.join(case.forbidden)}" if case.forbidden else ""
        print(f"{number:>2}. [{case.language}] {case.question}")
        print(f"    expected: {expected}{forbidden}")
        for gap, outcome in outcomes.items():
            mark = "ok" if judge(case, outcome) else "WRONG"
            head = f"    gap {gap_label(gap):<4} {mark:<5} ({outcome.passages} passages)"
            if outcome.refused is not None:
                print(f"{head} REFUSED ({outcome.refused})")
                continue
            print(f"{head} {outcome.answer}")
            print(f"{'':16}sources: {', '.join(outcome.sources) or 'none'}")
            print(f"{'':16}critic: {', '.join(outcome.issues) or 'no issue'}")
        print()
    for line in writer_summary(results, WRITER_GAPS):
        print(line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="backend address")
    parser.add_argument("--writer", action="store_true", help="run the Writer and the Critic")
    parser.add_argument(
        "--all-documents", action="store_true", help="search every indexed document"
    )
    args = parser.parse_args()
    settings = get_settings()
    min_score = settings.retrieval_min_score
    top_k = settings.retrieval_top_k

    with httpx2.Client(base_url=args.url, timeout=300.0) as client:
        try:
            document_ids = None if args.all_documents else demo_document_ids(client)
            scope = "all documents" if document_ids is None else f"{len(document_ids)} demo files"
            print(f"Searching {scope}\n")
            if args.writer:
                run_writer_part(client, top_k, document_ids, min_score)
            else:
                run_search_part(client, top_k, document_ids, min_score)
        except httpx2.HTTPError as error:
            print(f"Request failed: {error}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())