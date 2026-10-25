"""Measure whether splitting page 4 of the demo contract at its clauses fixes scenario 1.

With the current chunking, the best passage for "What is the termination
notice period?" holds Article 4.3 (60 days' notice) and the start of Article
4.4 (30 days to remedy a breach), and qwen2.5:3b presents the 30 days as a
notice period. probe_margin showed that sending fewer passages does not help.

This script sends hand-built passages of page 4 to the real Writer and Critic,
without any search, to see whether the model answers right once Article 4.4 is
in a passage of its own:
- current:        the first chunk of page 4, as the chunker cuts it today;
- 4.1-4.3:        only Articles 4.1 to 4.3 (no 30 days at all);
- 4.1-4.3 + 4.4:  Articles 4.1 to 4.3, then Article 4.4 in a second passage;
- 4.4 + 4.1-4.3:  the same two passages in the other order;
- split page:     the whole page cut before 4.4 and before 4.5 (three passages).

If the split variants answer 60 days, chunking at clause numbers would fix the
scenario; if even 4.1-4.3 alone fails, the cause is the model.

The page is read from demo_documents/ with ATLAS's parser and chunker (no
database, no server). The Writer and the Critic call Ollama with the local
settings (.env). Nothing is saved.

Usage, from backend/ with Ollama running (the server is not needed):
    python -m scripts.probe_clauses
"""

import sys
from pathlib import Path

from app.agents.critic import Critic
from app.agents.writer import Writer
from app.core.config import get_settings
from app.core.providers import build_llm_provider
from app.ingestion.chunking import ChunkOptions, chunk_pages
from app.ingestion.file_types import detect_file_type
from app.ingestion.models import ParseOptions
from app.ingestion.parsing import parse_document
from app.retrieval.retriever import RetrievedPassage
from scripts.probe_margin import WRITER_CASES, judge, run_plan

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo_documents"
CONTRACT = "service_agreement.pdf"
PAGE = 4
CAUSE = "4.4 Termination for cause"
EFFECTS = "4.5 Effects of termination"
# Scenario 1, in English and in French.
CASES = WRITER_CASES[:2]


def clause_variants(page_text: str, first_chunk: str) -> dict[str, list[str]]:
    """The passages sent to the Writer for each variant, in order.

    Raises:
        ValueError: If the page does not hold Articles 4.4 and 4.5 in this order.
    """
    cause = page_text.find(CAUSE)
    effects = page_text.find(EFFECTS)
    if cause < 0 or effects < cause:
        raise ValueError(f"Page {PAGE} does not hold {CAUSE!r} then {EFFECTS!r}")
    before, article_4_4, after = page_text[:cause], page_text[cause:effects], page_text[effects:]
    return {
        "current": [first_chunk],
        "4.1-4.3": [before],
        "4.1-4.3 + 4.4": [before, article_4_4],
        "4.4 + 4.1-4.3": [article_4_4, before],
        "split page": [before, article_4_4, after],
    }


def as_passages(texts: list[str]) -> list[RetrievedPassage]:
    """Passages as the search would return them (all from page 4)."""
    return [
        RetrievedPassage(
            chunk_id=f"probe-{position}",
            document_id="probe",
            filename=CONTRACT,
            page_number=PAGE,
            position=position,
            text=text,
            score=0.6,  # not a search: the score is not used by the Writer or the Critic
        )
        for position, text in enumerate(texts)
    ]


def load_page() -> tuple[str, str]:
    """Page 4 of the contract and its first chunk, exactly as an upload reads them."""
    path = DEMO_DIR / CONTRACT
    detected = detect_file_type(path, CONTRACT)
    pages = parse_document(path, detected.file_type, ParseOptions())
    page = next(page for page in pages if page.page_number == PAGE)
    first = next(
        chunk for chunk in chunk_pages(pages, ChunkOptions()) if chunk.page_number == PAGE
    )
    return page.text, first.text


def main() -> int:
    page_text, first_chunk = load_page()
    try:
        variants = clause_variants(page_text, first_chunk)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    settings = get_settings()
    llm = build_llm_provider(settings)
    writer = Writer(llm)
    critic = Critic(llm, use_model=settings.critic_use_llm)

    right: dict[str, int] = dict.fromkeys(variants, 0)
    for case in CASES:
        print(f"[{case.language}] {case.question}")
        for name, texts in variants.items():
            outcome = run_plan(writer, critic, case.question, as_passages(texts))
            ok = judge(case, outcome)
            right[name] += ok
            mark = "ok" if ok else "WRONG"
            text = f"REFUSED ({outcome.refused})" if outcome.refused else outcome.answer
            print(f"    {name:<14} {mark:<5} {text}")
            print(f"    {'':<20}critic: {', '.join(outcome.issues) or 'no issue'}")
        print()
    for name, count in right.items():
        print(f"{name:<14} {count} of {len(CASES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())