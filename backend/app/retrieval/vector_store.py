"""Storage-agnostic interface for chunk vectors, with an embedded Chroma implementation.

The vector store only keeps vectors and a few metadata fields. The chunk text
lives in SQLite (the source of truth), under the same id.
"""

import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings
from chromadb.errors import ChromaError

COLLECTION_PREFIX = "chunks_"
MODEL_METADATA_KEY = "embedding_model"


class VectorStoreError(Exception):
    """Raised when the vector store cannot complete an operation."""


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """One chunk vector to store, with the metadata needed to filter and cite it."""

    id: str  # same id as the chunk row in SQLite
    embedding: list[float]
    document_id: str
    page_number: int
    position: int


@dataclass(frozen=True, slots=True)
class VectorMatch:
    """One search result. A higher score means a closer match."""

    id: str
    score: float  # cosine similarity, between -1 and 1
    document_id: str
    page_number: int
    position: int


class VectorStore(ABC):
    """Common interface implemented by every vector store."""

    @abstractmethod
    def upsert(self, records: Sequence[VectorRecord]) -> None:
        """Add the records, replacing any record that already has the same id."""

    @abstractmethod
    def query(
        self,
        embedding: list[float],
        top_k: int,
        document_ids: Sequence[str] | None = None,
    ) -> list[VectorMatch]:
        """Return the top_k closest records, best first.

        document_ids=None searches every document; an empty list searches none.
        """

    @abstractmethod
    def delete_document(self, document_id: str) -> None:
        """Remove every record of one document. Unknown ids are ignored."""

    @abstractmethod
    def count(self) -> int:
        """Return the number of stored records."""


def collection_name_for(embedding_model: str) -> str:
    """Turn a model name into a valid Chroma collection name.

    Chroma only accepts letters, digits, ".", "_" and "-", so for example
    "openai/text-embedding-3-small" becomes "chunks_openai-text-embedding-3-small".
    """
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", embedding_model)
    cleaned = re.sub(r"\.{2,}", ".", cleaned).strip("._-")
    if not cleaned:
        raise ValueError(f"Cannot build a collection name from model {embedding_model!r}.")
    return f"{COLLECTION_PREFIX}{cleaned}"[:512]


class ChromaVectorStore(VectorStore):
    """Embedded Chroma (no server), persisted in a folder on disk.

    There is one collection per embedding model, and the exact model name is
    saved in the collection metadata. Vectors from two different models are
    never mixed: changing the model means re-indexing from SQLite.
    """

    def __init__(self, path: Path, embedding_model: str) -> None:
        self.embedding_model = embedding_model
        path.mkdir(parents=True, exist_ok=True)
        try:
            self._client = chromadb.PersistentClient(
                path=str(path),
                # Local-first: never send usage statistics.
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._open_collection(collection_name_for(embedding_model))
        except ChromaError as exc:
            raise VectorStoreError(f"Cannot open the vector store: {exc}") from exc

    def _open_collection(self, name: str) -> Collection:
        collection = self._client.get_or_create_collection(
            name=name,
            # Vectors are computed by our own EmbeddingProvider, never by Chroma.
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={MODEL_METADATA_KEY: self.embedding_model},
        )
        # An existing collection keeps its original metadata. Two model names
        # can give the same collection name after cleaning: refuse to mix them.
        stored_model = (collection.metadata or {}).get(MODEL_METADATA_KEY)
        if stored_model != self.embedding_model:
            raise VectorStoreError(
                f"Collection {name!r} was built with the model {stored_model!r}, "
                f"not {self.embedding_model!r}. Re-index the documents."
            )
        return collection

    def upsert(self, records: Sequence[VectorRecord]) -> None:
        if not records:
            return
        batch_size = self._client.get_max_batch_size()
        try:
            for start in range(0, len(records), batch_size):
                batch = records[start : start + batch_size]
                self._collection.upsert(
                    ids=[record.id for record in batch],
                    embeddings=[record.embedding for record in batch],
                    metadatas=[
                        {
                            "document_id": record.document_id,
                            "page_number": record.page_number,
                            "position": record.position,
                        }
                        for record in batch
                    ],
                )
        except ChromaError as exc:
            raise VectorStoreError(f"Cannot store vectors: {exc}") from exc

    def query(
        self,
        embedding: list[float],
        top_k: int,
        document_ids: Sequence[str] | None = None,
    ) -> list[VectorMatch]:
        if top_k < 1:
            raise ValueError("top_k must be at least 1.")
        if document_ids is not None and not document_ids:
            return []
        where = None if document_ids is None else {"document_id": {"$in": list(document_ids)}}
        try:
            result = self._collection.query(
                query_embeddings=[embedding],
                n_results=top_k,
                where=where,
                include=["metadatas", "distances"],
            )
        except ChromaError as exc:
            raise VectorStoreError(f"Vector search failed: {exc}") from exc

        ids = result["ids"][0]
        metadatas = (result["metadatas"] or [[]])[0]
        distances = (result["distances"] or [[]])[0]
        return [
            VectorMatch(
                id=record_id,
                # Chroma's cosine distance is 1 - cosine similarity.
                score=1.0 - float(distance),
                document_id=str(metadata["document_id"]),
                page_number=int(metadata["page_number"]),
                position=int(metadata["position"]),
            )
            for record_id, metadata, distance in zip(ids, metadatas, distances, strict=True)
        ]

    def delete_document(self, document_id: str) -> None:
        try:
            self._collection.delete(where={"document_id": document_id})
        except ChromaError as exc:
            raise VectorStoreError(f"Cannot delete vectors: {exc}") from exc

    def count(self) -> int:
        return self._collection.count()