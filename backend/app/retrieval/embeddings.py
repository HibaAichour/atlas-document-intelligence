"""Provider-agnostic interface for text embeddings, with two implementations."""

from abc import ABC, abstractmethod
from typing import Any

import httpx2

from app.core.http_errors import describe_http_error


class EmbeddingError(Exception):
    """Raised when a provider cannot return embeddings."""


class EmbeddingProvider(ABC):
    """Common interface implemented by every embedding provider."""

    name: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order.

        Raises:
            EmbeddingError: If the provider is unreachable or answers unexpectedly.
        """


def _post_json(
    client: httpx2.Client, path: str, payload: dict[str, Any], headers: dict[str, str]
) -> Any:
    """Send a JSON request and return the decoded JSON response."""
    try:
        response = client.post(path, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except httpx2.HTTPError as exc:
        raise EmbeddingError(f"Embedding request failed: {describe_http_error(exc)}") from exc
    except ValueError as exc:
        raise EmbeddingError("Embedding API returned a response that is not valid JSON") from exc


def _check_count(vectors: list[list[float]], texts: list[str]) -> list[list[float]]:
    """Make sure the provider returned exactly one vector per text."""
    if len(vectors) != len(texts):
        raise EmbeddingError(f"Expected {len(texts)} embeddings, received {len(vectors)}")
    return vectors


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Calls the native Ollama embedding API (POST /api/embed)."""

    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        timeout_seconds: float = 120.0,
        client: httpx2.Client | None = None,
    ) -> None:
        self.model = model
        self._client = client or httpx2.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = _post_json(self._client, "/api/embed", {"model": self.model, "input": texts}, {})
        try:
            vectors = [list(map(float, vector)) for vector in data["embeddings"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingError("Unexpected response format from Ollama") from exc
        return _check_count(vectors, texts)


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """Calls POST {base_url}/embeddings with the OpenAI request format."""

    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        client: httpx2.Client | None = None,
    ) -> None:
        self.model = model
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._client = client or httpx2.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        data = _post_json(
            self._client, "/embeddings", {"model": self.model, "input": texts}, self._headers
        )
        try:
            items = _in_input_order(data["data"])
            vectors = [list(map(float, item["embedding"])) for item in items]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingError("Unexpected response format from the embedding API") from exc
        return _check_count(vectors, texts)


def _in_input_order(items: list[Any]) -> list[Any]:
    """Return the response items in the order of the input texts.

    Most providers give each item an "index" (its position in the input), and
    may return the items in any order. The Gemini API leaves out an index equal
    to 0, as its format omits default values: with several texts, the first
    item has no index and the others have 1, 2, ... A missing index is
    therefore read as 0. When no item has an index at all, the items are taken
    in the order received, as the OpenAI API also guarantees.

    Raises:
        EmbeddingError: If the indices are not exactly 0 to n-1, each once
            (two items without an index, a gap, or a value out of range).
    """
    if not any(isinstance(item, dict) and "index" in item for item in items):
        return list(items)
    found: list[object] = [
        item.get("index", 0) if isinstance(item, dict) else None for item in items
    ]
    positions = [value for value in found if isinstance(value, int) and not isinstance(value, bool)]
    if len(positions) != len(items) or sorted(positions) != list(range(len(items))):
        raise EmbeddingError(f"Embedding API returned invalid indices: {found}")
    ordered: list[Any] = [None] * len(items)
    for position, item in zip(positions, items, strict=True):
        ordered[position] = item
    return ordered