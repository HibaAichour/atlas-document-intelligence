"""The embedding comparison script: corpus, scoring, summaries and Ollama helpers."""

import json
from pathlib import Path

import httpx2
import pytest

from app.retrieval.embeddings import EmbeddingError
from scripts.probe_embeddings import (
    CANDIDATES,
    DEMO_DIR,
    DEMO_FILES,
    QUESTION_SETS,
    Candidate,
    CorpusChunk,
    QuestionSet,
    ScoredChunk,
    cosine,
    load_corpus,
    loaded_memory_mb,
    measure,
    rank,
    report_lines,
    score_question,
    summarize,
    unload,
)
from tests.builders import make_pdf
from tests.conftest import HashEmbeddingProvider, UnavailableEmbeddingProvider

CORPUS = [
    CorpusChunk("contract.pdf", 1, "The agreement starts on 1 March 2026."),
    CorpusChunk("contract.pdf", 4, "The termination notice period is 60 days."),
    CorpusChunk("minutes.pdf", 2, "Le raccordement de Marseille coûte 17 100,00 USD."),
]


def ranked(*scores: tuple[float, str, int]) -> list[ScoredChunk]:
    return [ScoredChunk(score, CorpusChunk(name, page, "text")) for score, name, page in scores]


def test_cosine() -> None:
    assert cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 2.0]) == pytest.approx(0.0)
    assert cosine([1.0, 1.0], [2.0, 2.0]) == pytest.approx(1.0)
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_rank_puts_the_closest_chunk_first() -> None:
    vectors = [[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]]

    ranking = rank([0.0, 1.0], vectors, CORPUS)

    assert [item.chunk.page_number for item in ranking] == [4, 2, 1]
    assert ranking[0].score == pytest.approx(1.0)


def test_score_question_finds_the_best_right_passage() -> None:
    ranking = ranked((0.8, "review.pptx", 6), (0.7, "contract.pdf", 4), (0.6, "contract.pdf", 1))

    result = score_question("Notice?", 4, "contract.pdf", ranking)

    assert result.right_score == pytest.approx(0.7)
    assert result.right_rank == 2


def test_score_question_accepts_several_pages_and_absent_answers() -> None:
    ranking = ranked((0.8, "contract.pdf", 3), (0.7, "contract.pdf", 5))

    assert score_question("Q", (5, 3), "contract.pdf", ranking).right_rank == 1
    absent = score_question("Salary?", None, "contract.pdf", ranking)
    assert absent.pages == ()
    assert absent.right_score is None
    # The right file on the wrong page does not count.
    assert score_question("Q", 6, "contract.pdf", ranking).right_rank is None


def test_summarize_counts_first_missed_and_gap() -> None:
    results = [
        score_question("A", 4, "c.pdf", ranked((0.80, "c.pdf", 4))),
        score_question("B", 1, "c.pdf", ranked((0.75, "o.pdf", 2), (0.70, "c.pdf", 1))),
        # Right passage at rank 6: outside the top 5 the Writer receives.
        score_question(
            "C",
            2,
            "c.pdf",
            ranked(*[(0.9 - i / 100, "o.pdf", 9) for i in range(5)], (0.5, "c.pdf", 2)),
        ),
        score_question("D", None, "c.pdf", ranked((0.62, "c.pdf", 3))),
        score_question("E", None, "c.pdf", ranked((0.55, "c.pdf", 3))),
    ]

    summary = summarize("test", results)

    assert (summary.answerable, summary.first, summary.missed) == (3, 1, 1)
    assert summary.lowest_right == pytest.approx(0.5)
    assert summary.highest_absent == pytest.approx(0.62)
    assert summary.gap == pytest.approx(-0.12)


def test_summary_gap_is_none_without_absent_questions() -> None:
    summary = summarize("only answerable", [score_question("A", 4, "c.pdf", ranked())])

    assert summary.lowest_right is None
    assert summary.missed == 1
    assert summary.gap is None


def test_measure_uses_the_prefixes_and_reports_every_set() -> None:
    provider = HashEmbeddingProvider()
    seen: list[str] = []
    original = provider.embed

    def recording_embed(texts: list[str]) -> list[list[float]]:
        seen.extend(texts)
        return original(texts)

    provider.embed = recording_embed  # type: ignore[method-assign]
    candidate = Candidate("fake", document_prefix="doc: ", query_prefix="query: ")
    sets = [QuestionSet("small", "contract.pdf", [("termination notice period", 4)])]
    ticks = iter([10.0, 12.5])

    report = measure(
        candidate,
        provider,
        CORPUS,
        sets,
        memory_reader=lambda model: 321.0,
        clock=lambda: next(ticks),
    )

    assert seen[:3] == ["doc: " + chunk.text for chunk in CORPUS]
    assert seen[3] == "query: termination notice period"
    assert report.chunk_count == 3
    assert report.embed_seconds == pytest.approx(2.5)
    assert report.memory_mb == 321.0
    assert report.summaries[0].first == 1
    lines = report_lines(report, show_details=True)
    assert lines[0] == "== fake"
    assert "3 chunks embedded in 2.5 s, memory 321 MB" in lines[1]
    assert any("right passage:" in line and "(rank 1)" in line for line in lines)


def test_measure_raises_when_the_model_fails() -> None:
    with pytest.raises(EmbeddingError):
        measure(Candidate("missing"), UnavailableEmbeddingProvider(), CORPUS, QUESTION_SETS)


def test_loaded_memory_reads_ollama_ps() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.url.path == "/api/ps"
        models = [
            {"name": "qwen2.5:3b", "size": 2_500_000_000},
            {"name": "bge-m3:latest", "size": 1_200_000_000},
        ]
        return httpx2.Response(200, json={"models": models})

    client = httpx2.Client(base_url="http://ollama", transport=httpx2.MockTransport(handler))

    assert loaded_memory_mb(client, "bge-m3") == pytest.approx(1200.0)
    assert loaded_memory_mb(client, "qwen2.5:3b") == pytest.approx(2500.0)
    assert loaded_memory_mb(client, "granite-embedding:278m") is None


def test_loaded_memory_is_none_when_ollama_fails() -> None:
    client = httpx2.Client(
        base_url="http://ollama",
        transport=httpx2.MockTransport(lambda request: httpx2.Response(500)),
    )

    assert loaded_memory_mb(client, "bge-m3") is None


def test_unload_asks_ollama_to_free_the_model() -> None:
    bodies: list[dict] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return httpx2.Response(200, json={"embeddings": [[0.1]]})

    client = httpx2.Client(base_url="http://ollama", transport=httpx2.MockTransport(handler))

    unload(client, "bge-m3")

    assert bodies == [{"model": "bge-m3", "input": ["x"], "keep_alive": 0}]


def test_load_corpus_chunks_each_page(tmp_path: Path) -> None:
    make_pdf(tmp_path / "a.pdf", ["First page text.", "Second page text."])

    corpus = load_corpus(tmp_path, ["a.pdf"])

    assert [(chunk.filename, chunk.page_number) for chunk in corpus] == [
        ("a.pdf", 1),
        ("a.pdf", 2),
    ]


def test_question_sets_target_existing_demo_documents() -> None:
    for question_set in QUESTION_SETS:
        assert question_set.filename in DEMO_FILES
        assert any(expected is not None for _, expected in question_set.questions)
        assert any(expected is None for _, expected in question_set.questions)
    for filename in DEMO_FILES:
        assert (DEMO_DIR / filename).is_file()


def test_candidates_start_with_the_current_model() -> None:
    assert CANDIDATES[0].model == "nomic-embed-text"
    assert CANDIDATES[0].query_prefix == "search_query: "
    assert len({candidate.model for candidate in CANDIDATES}) == len(CANDIDATES)