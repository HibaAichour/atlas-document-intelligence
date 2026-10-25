"""Compare embedding models on the demo documents, in English, French and across both.

Used to choose a multilingual embedding model (step 10 bis). The script works
on its own: it reads the demo documents with the ATLAS parsers and chunker,
embeds every chunk with each model, and scores the questions by cosine
similarity in memory, as Chroma does. Neither the database nor the index is
touched, and the backend server does not need to run (Ollama does).

For each model and each question set, it prints:
- the lowest score of a right passage (expected file and page);
- the highest best score of a question the documents cannot answer;
- the gap between the two (the room left for a threshold; compare gaps, not
  raw scores, since every model has its own similarity scale);
- how often the right passage ranks first, and how often it is not in the
  top 5 (the passages the Writer would receive);
- the time to embed all chunks and the memory of the loaded model.

Usage, from backend/ while Ollama is running:
    python -m scripts.probe_embeddings
    python -m scripts.probe_embeddings --models bge-m3 nomic-embed-text
    python -m scripts.probe_embeddings --models bge-m3 --details

Each model is unloaded from Ollama after its measures, so two embedding
models never sit in memory at the same time.
"""

import argparse
import math
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import httpx2

from app.ingestion.chunking import ChunkOptions, chunk_pages
from app.ingestion.file_types import detect_file_type
from app.ingestion.models import ParseOptions
from app.ingestion.parsing import parse_document
from app.retrieval.embedder import Embedder
from app.retrieval.embeddings import EmbeddingError, EmbeddingProvider, OllamaEmbeddingProvider
from scripts.probe_scores import (
    CONTRACT_FR_QUESTIONS,
    CONTRACT_QUESTIONS,
    MINUTES_EN_QUESTIONS,
    MINUTES_FR_QUESTIONS,
    REVIEW_QUESTIONS,
    Expected,
    expected_pages,
)

DEMO_DIR = Path(__file__).resolve().parents[2] / "demo_documents"
DEMO_FILES = (
    "service_agreement.pdf",
    "invoice_HDS-INV-2026-0042.pdf",
    "quarterly_review_HDS_Q2_2026.pptx",
    "compte_rendu_copil_HDS_2026-07.pdf",
)
CONTRACT = "service_agreement.pdf"
REVIEW = "quarterly_review_HDS_Q2_2026.pptx"
MINUTES = "compte_rendu_copil_HDS_2026-07.pdf"

# Number of passages the Writer receives (RETRIEVAL_TOP_K).
TOP_K = 5


@dataclass(frozen=True)
class Candidate:
    """An Ollama embedding model with the task prefixes it was trained with."""

    model: str
    document_prefix: str = ""
    query_prefix: str = ""


CANDIDATES = (
    Candidate("nomic-embed-text", "search_document: ", "search_query: "),
    Candidate("nomic-embed-text-v2-moe", "search_document: ", "search_query: "),
    Candidate("bge-m3"),
    Candidate("granite-embedding:278m"),
)

# --- Question sets (defined in probe_scores, shared with the server probe) -----


@dataclass(frozen=True)
class QuestionSet:
    name: str
    filename: str  # the document that holds the answers
    questions: list[tuple[str, Expected]]


QUESTION_SETS = (
    QuestionSet("contract EN", CONTRACT, CONTRACT_QUESTIONS),
    QuestionSet("review EN", REVIEW, REVIEW_QUESTIONS),
    QuestionSet("minutes FR", MINUTES, MINUTES_FR_QUESTIONS),
    QuestionSet("contract FR>EN", CONTRACT, CONTRACT_FR_QUESTIONS),
    QuestionSet("minutes EN>FR", MINUTES, MINUTES_EN_QUESTIONS),
)

# --- Corpus and scoring (pure functions) ----------------------------------------


@dataclass(frozen=True)
class CorpusChunk:
    filename: str
    page_number: int
    text: str


@dataclass(frozen=True)
class ScoredChunk:
    score: float
    chunk: CorpusChunk


def load_corpus(directory: Path, filenames: Sequence[str]) -> list[CorpusChunk]:
    """Parse and chunk the demo documents exactly as an upload does."""
    corpus: list[CorpusChunk] = []
    for filename in filenames:
        path = directory / filename
        detected = detect_file_type(path, filename)
        pages = parse_document(path, detected.file_type, ParseOptions())
        for chunk in chunk_pages(pages, ChunkOptions()):
            corpus.append(CorpusChunk(filename, chunk.page_number, chunk.text))
    return corpus


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norms = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norms if norms else 0.0


def rank(
    query: Sequence[float], vectors: Sequence[Sequence[float]], corpus: Sequence[CorpusChunk]
) -> list[ScoredChunk]:
    """Every chunk with its score, best first."""
    scored = [
        ScoredChunk(cosine(query, vector), chunk)
        for vector, chunk in zip(vectors, corpus, strict=True)
    ]
    return sorted(scored, key=lambda item: item.score, reverse=True)


def is_right(item: ScoredChunk, filename: str, pages: tuple[int, ...]) -> bool:
    return item.chunk.filename == filename and item.chunk.page_number in pages


@dataclass(frozen=True)
class QuestionResult:
    question: str
    pages: tuple[int, ...]  # empty when the documents do not hold the answer
    ranking: list[ScoredChunk]
    right_score: float | None  # best score of a right passage
    right_rank: int | None  # 1-based rank of the best right passage


def score_question(
    question: str,
    expected: Expected,
    filename: str,
    ranking: list[ScoredChunk],
) -> QuestionResult:
    pages = expected_pages(expected)
    for index, item in enumerate(ranking):
        if pages and is_right(item, filename, pages):
            return QuestionResult(question, pages, ranking, item.score, index + 1)
    return QuestionResult(question, pages, ranking, None, None)


@dataclass(frozen=True)
class SetSummary:
    name: str
    answerable: int
    first: int  # right passage ranked first
    missed: int  # right passage outside the top TOP_K
    lowest_right: float | None
    highest_absent: float | None

    @property
    def gap(self) -> float | None:
        if self.lowest_right is None or self.highest_absent is None:
            return None
        return self.lowest_right - self.highest_absent


def summarize(name: str, results: Sequence[QuestionResult]) -> SetSummary:
    answerable = [result for result in results if result.pages]
    absent = [result for result in results if not result.pages]
    right_scores = [r.right_score for r in answerable if r.right_score is not None]
    absent_scores = [r.ranking[0].score for r in absent if r.ranking]
    return SetSummary(
        name=name,
        answerable=len(answerable),
        first=sum(1 for r in answerable if r.right_rank == 1),
        missed=sum(1 for r in answerable if r.right_rank is None or r.right_rank > TOP_K),
        lowest_right=min(right_scores) if right_scores else None,
        highest_absent=max(absent_scores) if absent_scores else None,
    )


def _number(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "-"
    return f"{value:+.3f}" if signed else f"{value:.3f}"


def summary_table(summaries: Sequence[SetSummary]) -> list[str]:
    lines = [f"  {'set':<16}{'right min':>10}{'absent max':>12}{'gap':>9}{'first':>9}{'missed':>8}"]
    for item in summaries:
        lines.append(
            f"  {item.name:<16}{_number(item.lowest_right):>10}"
            f"{_number(item.highest_absent):>12}{_number(item.gap, signed=True):>9}"
            f"{f'{item.first}/{item.answerable}':>9}{item.missed:>8}"
        )
    return lines


def detail_lines(result: QuestionResult) -> list[str]:
    label = "p." + ",".join(map(str, result.pages)) if result.pages else "absent"
    top = " | ".join(
        f"{item.score:.3f} {item.chunk.filename[:22]} p.{item.chunk.page_number}"
        for item in result.ranking[:3]
    )
    lines = [f"    [{label:>6}] {result.question}", f"             {top}"]
    if result.pages:
        if result.right_score is None:
            lines.append("             right passage: not found")
        else:
            lines.append(
                f"             right passage: {result.right_score:.3f} (rank {result.right_rank})"
            )
    return lines


# --- Measures with a real model -------------------------------------------------


@dataclass(frozen=True)
class ModelReport:
    candidate: Candidate
    chunk_count: int
    embed_seconds: float
    memory_mb: float | None
    summaries: list[SetSummary]
    details: list[tuple[str, list[QuestionResult]]]


def measure(
    candidate: Candidate,
    provider: EmbeddingProvider,
    corpus: Sequence[CorpusChunk],
    question_sets: Sequence[QuestionSet] = QUESTION_SETS,
    memory_reader: Callable[[str], float | None] = lambda model: None,
    clock: Callable[[], float] = time.perf_counter,
) -> ModelReport:
    """Embed the corpus and every question with one model, then score them.

    Raises:
        EmbeddingError: If the model cannot be reached or is not installed.
    """
    embedder = Embedder(
        provider,
        document_prefix=candidate.document_prefix,
        query_prefix=candidate.query_prefix,
    )
    start = clock()
    vectors = embedder.embed_documents([chunk.text for chunk in corpus])
    embed_seconds = clock() - start
    memory_mb = memory_reader(candidate.model)

    summaries: list[SetSummary] = []
    details: list[tuple[str, list[QuestionResult]]] = []
    for question_set in question_sets:
        results = [
            score_question(
                question,
                expected,
                question_set.filename,
                rank(embedder.embed_query(question), vectors, corpus),
            )
            for question, expected in question_set.questions
        ]
        summaries.append(summarize(question_set.name, results))
        details.append((question_set.name, results))
    return ModelReport(candidate, len(corpus), embed_seconds, memory_mb, summaries, details)


def loaded_memory_mb(client: httpx2.Client, model: str) -> float | None:
    """Memory of a loaded model, as shown by `ollama ps` (None if unknown)."""
    try:
        response = client.get("/api/ps")
        response.raise_for_status()
        models = response.json().get("models", [])
    except (httpx2.HTTPError, ValueError):
        return None
    for entry in models:
        name = str(entry.get("name", ""))
        # "bge-m3" is listed as "bge-m3:latest".
        if name == model or name == f"{model}:latest":
            return float(entry.get("size", 0)) / 1_000_000
    return None


def unload(client: httpx2.Client, model: str) -> None:
    """Ask Ollama to free the model's memory right away (best effort)."""
    try:
        client.post("/api/embed", json={"model": model, "input": ["x"], "keep_alive": 0})
    except httpx2.HTTPError:
        pass


def report_lines(report: ModelReport, show_details: bool) -> list[str]:
    memory = "unknown" if report.memory_mb is None else f"{report.memory_mb:,.0f} MB"
    lines = [
        f"== {report.candidate.model}",
        f"  {report.chunk_count} chunks embedded in {report.embed_seconds:.1f} s, memory {memory}",
        *summary_table(report.summaries),
    ]
    if show_details:
        for name, results in report.details:
            lines.append(f"  -- {name}")
            for result in results:
                lines.extend(detail_lines(result))
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ollama", default="http://127.0.0.1:11434", help="Ollama address")
    parser.add_argument(
        "--models",
        nargs="+",
        choices=[candidate.model for candidate in CANDIDATES],
        default=[candidate.model for candidate in CANDIDATES],
        help="models to compare",
    )
    parser.add_argument("--details", action="store_true", help="print every question")
    args = parser.parse_args()

    print("Reading the demo documents (the invoice goes through OCR)...")
    corpus = load_corpus(DEMO_DIR, DEMO_FILES)
    print(f"{len(corpus)} chunks from {len(DEMO_FILES)} documents, top-k = {TOP_K}")
    print()

    failures = 0
    with httpx2.Client(base_url=args.ollama, timeout=300.0) as client:
        for candidate in CANDIDATES:
            if candidate.model not in args.models:
                continue
            provider = OllamaEmbeddingProvider(args.ollama, candidate.model, timeout_seconds=300)
            try:
                report = measure(
                    candidate,
                    provider,
                    corpus,
                    memory_reader=lambda model: loaded_memory_mb(client, model),
                )
            except EmbeddingError as error:
                print(f"== {candidate.model}\n  failed: {error}\n")
                failures += 1
                continue
            finally:
                unload(client, candidate.model)
            print("\n".join(report_lines(report, args.details)))
            print()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())