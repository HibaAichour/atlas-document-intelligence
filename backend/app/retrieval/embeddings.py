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
            # Items carry an "index"; sort on it so vectors match the input order.
            items = sorted(data["data"], key=lambda item: item["index"])
            vectors = [list(map(float, item["embedding"])) for item in items]
        except (KeyError, TypeError, ValueError) as exc:
            raise EmbeddingError("Unexpected response format from the embedding API") from exc
        return _check_count(vectors, texts)