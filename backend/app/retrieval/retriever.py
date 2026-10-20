"""Find the passages closest to a question, with their source document and page."""

from collections.abc import Sequence
from dataclasses import dataclass

from app.db.repositories import DocumentRepository
from app.retrieval.embedder import Embedder
from app.retrieval.embeddings import EmbeddingError
from app.retrieval.vector_store import VectorStore, VectorStoreError


class RetrievalError(Exception):
    """The search could not run. The message is safe to show to the user."""


@dataclass(frozen=True, slots=True)
class RetrievedPassage:
    """A chunk found by the search, ready to be shown or cited."""

    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    position: int
    text: str
    score: float  # cosine similarity: higher means closer to the question


class Retriever:
    """Embeds the question, queries the vector store and reads the text from SQLite.

    This is a deterministic tool used by the Orchestrator, not an agent: it
    makes no decision. The text always comes from SQLite, the source of truth.
    """

    def __init__(self, embedder: Embedder, vector_store: VectorStore) -> None:
        self._embedder = embedder
        self._vector_store = vector_store

    def search(
        self,
        repository: DocumentRepository,
        query: str,
        top_k: int,
        document_ids: Sequence[str] | None = None,
    ) -> list[RetrievedPassage]:
        """Return up to top_k passages, best first.

        Raises:
            ValueError: If the query is empty or top_k is below 1.
            RetrievalError: If the embedding service or the vector store fails.
        """
        try:
            vector = self._embedder.embed_query(query)
            matches = self._vector_store.query(vector, top_k, document_ids)
        except (EmbeddingError, VectorStoreError) as error:
            raise RetrievalError(f"Search failed: {error}") from error

        # A vector whose chunk no longer exists in SQLite is skipped.
        chunks = {chunk.id: chunk for chunk in repository.get_chunks([m.id for m in matches])}
        return [
            RetrievedPassage(
                chunk_id=match.id,
                document_id=chunks[match.id].document_id,
                filename=chunks[match.id].document.filename,
                page_number=chunks[match.id].page_number,
                position=chunks[match.id].position,
                text=chunks[match.id].text,
                score=match.score,
            )
            for match in matches
            if match.id in chunks
        ]