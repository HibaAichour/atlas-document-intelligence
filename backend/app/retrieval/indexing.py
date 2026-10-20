"""Make a document searchable: chunk its pages, embed the chunks, store the vectors.

Used by the upload workflow and by the re-indexing script, so both always
index documents in exactly the same way.
"""

from collections.abc import Sequence

from app.db.models import Document
from app.db.repositories import DocumentRepository
from app.ingestion.chunking import ChunkOptions, chunk_pages
from app.ingestion.models import PageText
from app.retrieval.embedder import Embedder
from app.retrieval.embeddings import EmbeddingError
from app.retrieval.vector_store import VectorRecord, VectorStore, VectorStoreError


class IndexingError(Exception):
    """A document could not be indexed. The message is safe to show to the user."""


class DocumentIndexer:
    """Chunks, embeds and stores the pages of one document at a time."""

    def __init__(
        self,
        embedder: Embedder,
        vector_store: VectorStore,
        chunk_options: ChunkOptions | None = None,
    ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._chunk_options = chunk_options or ChunkOptions()

    @property
    def embedder(self) -> Embedder:
        return self._embedder

    @property
    def vector_store(self) -> VectorStore:
        return self._vector_store

    def index(
        self, repository: DocumentRepository, document: Document, pages: Sequence[PageText]
    ) -> int:
        """Replace the chunks and vectors of the document. Return the number of chunks.

        The vectors are computed before anything is written. If the embedding
        service is down, the chunks and vectors already stored are kept as
        they were.

        Raises:
            IndexingError: If the embeddings or the vector store fail.
        """
        chunks = chunk_pages(pages, self._chunk_options)
        try:
            vectors = self._embedder.embed_documents([chunk.text for chunk in chunks])
            stored = repository.replace_chunks(document, chunks)
            self._vector_store.delete_document(document.id)
            self._vector_store.upsert(
                [
                    VectorRecord(
                        id=chunk.id,
                        embedding=vector,
                        document_id=document.id,
                        page_number=chunk.page_number,
                        position=chunk.position,
                    )
                    for chunk, vector in zip(stored, vectors, strict=True)
                ]
            )
        except (EmbeddingError, VectorStoreError) as error:
            raise IndexingError(f"Indexing failed: {error}") from error
        return len(stored)

    def remove(self, document_id: str) -> None:
        """Remove the vectors of a document from the vector store.

        Raises:
            VectorStoreError: If the vector store fails.
        """
        self._vector_store.delete_document(document_id)