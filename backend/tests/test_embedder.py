"""Tests for the Embedder (prefixes and batching), with a fake provider: no network."""

import pytest

from app.core.config import Settings
from app.retrieval.embedder import Embedder
from app.retrieval.embeddings import EmbeddingError, EmbeddingProvider


class RecordingProvider(EmbeddingProvider):
    """Returns one small vector per text and remembers every request."""

    name = "recording"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[float(len(text)), 1.0] for text in texts]


class FailingProvider(EmbeddingProvider):
    name = "failing"

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("Embedding request failed: connection refused")


def test_document_prefix_is_added_to_every_chunk() -> None:
    provider = RecordingProvider()
    embedder = Embedder(provider, document_prefix="search_document: ", query_prefix="q: ")

    embedder.embed_documents(["First chunk.", "Second chunk."])

    assert provider.calls == [["search_document: First chunk.", "search_document: Second chunk."]]


def test_query_prefix_is_added_to_the_question() -> None:
    provider = RecordingProvider()
    embedder = Embedder(provider, document_prefix="d: ", query_prefix="search_query: ")

    vector = embedder.embed_query("  What is the notice period?  ")

    assert provider.calls == [["search_query: What is the notice period?"]]
    assert vector == [float(len("search_query: What is the notice period?")), 1.0]


def test_no_prefix_by_default() -> None:
    provider = RecordingProvider()
    embedder = Embedder(provider)

    embedder.embed_documents(["Chunk."])
    embedder.embed_query("Question?")

    assert provider.calls == [["Chunk."], ["Question?"]]


def test_documents_are_sent_in_batches_and_keep_their_order() -> None:
    provider = RecordingProvider()
    embedder = Embedder(provider, batch_size=2)
    texts = ["a", "bb", "ccc", "dddd", "eeeee"]

    vectors = embedder.embed_documents(texts)

    assert [len(call) for call in provider.calls] == [2, 2, 1]
    assert [vector[0] for vector in vectors] == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_no_text_means_no_request() -> None:
    provider = RecordingProvider()
    assert Embedder(provider).embed_documents([]) == []
    assert provider.calls == []


def test_an_empty_question_is_refused() -> None:
    with pytest.raises(ValueError):
        Embedder(RecordingProvider()).embed_query("   ")


def test_provider_errors_are_not_hidden() -> None:
    embedder = Embedder(FailingProvider())
    with pytest.raises(EmbeddingError, match="connection refused"):
        embedder.embed_documents(["Chunk."])


def test_batch_size_must_be_positive() -> None:
    with pytest.raises(ValueError):
        Embedder(RecordingProvider(), batch_size=0)


def test_default_settings_use_no_prefix_for_bge_m3(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("EMBEDDING_DOCUMENT_PREFIX", "EMBEDDING_QUERY_PREFIX"):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.embedding_document_prefix == ""
    assert settings.embedding_query_prefix == ""
    assert settings.embedding_batch_size == 32


def test_nomic_prefixes_can_be_set_with_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBEDDING_DOCUMENT_PREFIX", "search_document: ")
    monkeypatch.setenv("EMBEDDING_QUERY_PREFIX", "search_query: ")
    provider = RecordingProvider()

    embedder = Embedder.from_settings(provider, Settings(_env_file=None))
    embedder.embed_documents(["Chunk."])
    embedder.embed_query("Question?")

    assert provider.calls == [["search_document: Chunk."], ["search_query: Question?"]]