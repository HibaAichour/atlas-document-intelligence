"""Tests for the embedding providers, with the network replaced by a mock."""

import json

import httpx2
import pytest

from app.retrieval.embeddings import (
    EmbeddingError,
    OllamaEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)

OLLAMA_URL = "http://ollama.test"
OPENAI_URL = "http://llm.test/v1"


def mock_client(base_url: str, handler) -> httpx2.Client:
    """An HTTP client whose calls are answered by `handler`."""
    return httpx2.Client(base_url=base_url, transport=httpx2.MockTransport(handler))


def test_ollama_returns_one_vector_per_text() -> None:
    captured: dict = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]})

    provider = OllamaEmbeddingProvider(
        OLLAMA_URL, "nomic-embed-text", client=mock_client(OLLAMA_URL, handler)
    )
    vectors = provider.embed(["first", "second"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["path"] == "/api/embed"
    assert captured["body"] == {"model": "nomic-embed-text", "input": ["first", "second"]}


def test_openai_compatible_restores_input_order() -> None:
    captured: dict = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("Authorization")
        # Items deliberately returned out of order.
        return httpx2.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.3, 0.4]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ]
            },
        )

    provider = OpenAICompatibleEmbeddingProvider(
        OPENAI_URL, "embed-model", api_key="test-key", client=mock_client(OPENAI_URL, handler)
    )
    vectors = provider.embed(["first", "second"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["path"] == "/v1/embeddings"
    assert captured["auth"] == "Bearer test-key"


def test_openai_compatible_keeps_order_without_index() -> None:
    # The Gemini API returns its items in input order, without an "index".
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {"object": "embedding", "embedding": [0.1, 0.2]},
                    {"object": "embedding", "embedding": [0.3, 0.4]},
                ],
                "model": "gemini-embedding-001",
            },
        )

    provider = OpenAICompatibleEmbeddingProvider(
        OPENAI_URL, "gemini-embedding-001", client=mock_client(OPENAI_URL, handler)
    )

    assert provider.embed(["first", "second"]) == [[0.1, 0.2], [0.3, 0.4]]


def test_openai_compatible_reads_a_missing_index_as_zero() -> None:
    # The Gemini API leaves out "index" when it is 0: the first item has none.
    # The items are also shuffled here, to check that they are sorted.
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json={
                "data": [
                    {"object": "embedding", "index": 2, "embedding": [0.5, 0.6]},
                    {"object": "embedding", "embedding": [0.1, 0.2]},
                    {"object": "embedding", "index": 1, "embedding": [0.3, 0.4]},
                ]
            },
        )

    provider = OpenAICompatibleEmbeddingProvider(
        OPENAI_URL, "gemini-embedding-001", client=mock_client(OPENAI_URL, handler)
    )

    assert provider.embed(["first", "second", "third"]) == [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]


@pytest.mark.parametrize(
    "items",
    [
        # Two items without an index: both would be 0.
        [{"embedding": [0.1]}, {"embedding": [0.2]}, {"index": 1, "embedding": [0.3]}],
        # A gap: no item at position 1.
        [{"embedding": [0.1]}, {"index": 2, "embedding": [0.2]}],
        # Out of range, and not an integer.
        [{"index": 0, "embedding": [0.1]}, {"index": 5, "embedding": [0.2]}],
        [{"index": 0, "embedding": [0.1]}, {"index": "1", "embedding": [0.2]}],
    ],
)
def test_openai_compatible_rejects_invalid_indices(items: list[dict]) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"data": items})

    provider = OpenAICompatibleEmbeddingProvider(
        OPENAI_URL, "embed-model", client=mock_client(OPENAI_URL, handler)
    )

    with pytest.raises(EmbeddingError, match="invalid indices"):
        provider.embed([f"text {number}" for number in range(len(items))])


def test_openai_compatible_rejects_wrong_number_of_vectors_without_index() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]})

    provider = OpenAICompatibleEmbeddingProvider(
        OPENAI_URL, "embed-model", client=mock_client(OPENAI_URL, handler)
    )

    with pytest.raises(EmbeddingError, match="Expected 2 embeddings"):
        provider.embed(["first", "second"])


def test_empty_input_makes_no_request() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("No HTTP request expected for an empty input")

    provider = OllamaEmbeddingProvider(
        OLLAMA_URL, "nomic-embed-text", client=mock_client(OLLAMA_URL, handler)
    )

    assert provider.embed([]) == []


def test_wrong_number_of_vectors_raises_embedding_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"embeddings": [[0.1, 0.2]]})

    provider = OllamaEmbeddingProvider(
        OLLAMA_URL, "nomic-embed-text", client=mock_client(OLLAMA_URL, handler)
    )

    with pytest.raises(EmbeddingError):
        provider.embed(["first", "second"])


def test_server_error_raises_embedding_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(500, json={"error": "boom"})

    provider = OpenAICompatibleEmbeddingProvider(
        OPENAI_URL, "embed-model", client=mock_client(OPENAI_URL, handler)
    )

    with pytest.raises(EmbeddingError):
        provider.embed(["text"])