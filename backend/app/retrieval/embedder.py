"""Turn chunks and questions into vectors, with the task prefixes the model expects.

Some embedding models (like nomic-embed-text) are trained with a different
prefix for stored passages and for search questions. Using the right prefix
on each side noticeably improves retrieval. The prefixes live here, in the
retrieval layer, so the providers stay generic.
"""

from collections.abc import Sequence

from app.core.config import Settings
from app.retrieval.embeddings import EmbeddingProvider


class Embedder:
    """Adds task prefixes and sends texts to the provider in batches."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        *,
        document_prefix: str = "",
        query_prefix: str = "",
        batch_size: int = 32,
    ) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1.")
        self._provider = provider
        self._document_prefix = document_prefix
        self._query_prefix = query_prefix
        self._batch_size = batch_size

    @classmethod
    def from_settings(cls, provider: EmbeddingProvider, settings: Settings) -> "Embedder":
        """Build an embedder with the prefixes and batch size from the settings."""
        return cls(
            provider,
            document_prefix=settings.embedding_document_prefix,
            query_prefix=settings.embedding_query_prefix,
            batch_size=settings.embedding_batch_size,
        )

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per chunk text, in the same order.

        Raises:
            EmbeddingError: If the provider fails on any batch.
        """
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            vectors.extend(self._provider.embed([self._document_prefix + text for text in batch]))
        return vectors

    def embed_query(self, question: str) -> list[float]:
        """Return the vector of a search question.

        Raises:
            ValueError: If the question is empty.
            EmbeddingError: If the provider fails.
        """
        if not question.strip():
            raise ValueError("The question is empty.")
        return self._provider.embed([self._query_prefix + question.strip()])[0]