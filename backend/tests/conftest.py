"""Shared pytest fixtures."""

import hashlib
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_indexer
from app.core.config import get_settings
from app.db.session import create_db_engine, create_session_factory, init_db, sqlite_url
from app.ingestion.chunking import ChunkOptions
from app.main import app
from app.retrieval.embedder import Embedder
from app.retrieval.embeddings import EmbeddingError, EmbeddingProvider
from app.retrieval.indexing import DocumentIndexer
from app.retrieval.vector_store import ChromaVectorStore

FAKE_DIMENSION = 64
FAKE_MODEL = "fake-hash-embedding"


class HashEmbeddingProvider(EmbeddingProvider):
    """A fake embedding model: texts sharing words get similar vectors.

    Each word is hashed into one of 64 dimensions. It is deterministic,
    instant and needs no network, so tests never call Ollama.
    """

    name = "fake"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            vector = [0.0] * FAKE_DIMENSION
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                digest = hashlib.md5(word.encode(), usedforsecurity=False).digest()
                vector[digest[0] % FAKE_DIMENSION] += 1.0
            if not any(vector):
                vector[0] = 1.0  # a zero vector has no direction for cosine
            vectors.append(vector)
        return vectors


class UnavailableEmbeddingProvider(EmbeddingProvider):
    """Behaves like an embedding service that is not running."""

    name = "unavailable"

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("Embedding request failed: connection refused")


@pytest.fixture
def db_session(tmp_path: Path) -> Iterator[Session]:
    """A session on a fresh SQLite database, deleted after the test."""
    engine = create_db_engine(sqlite_url(tmp_path))
    init_db(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def make_indexer(tmp_path: Path) -> Callable[..., DocumentIndexer]:
    """Return a function that builds an indexer on a fresh, temporary Chroma.

    make_indexer() uses the fake embedding model;
    make_indexer(unavailable=True) simulates an embedding service that is down.
    """

    def factory(*, unavailable: bool = False, name: str = "default") -> DocumentIndexer:
        provider: EmbeddingProvider = (
            UnavailableEmbeddingProvider() if unavailable else HashEmbeddingProvider()
        )
        embedder = Embedder(
            provider, document_prefix="search_document: ", query_prefix="search_query: "
        )
        vector_store = ChromaVectorStore(tmp_path / f"chroma-{name}", FAKE_MODEL)
        return DocumentIndexer(embedder, vector_store, ChunkOptions())

    return factory


@pytest.fixture
def indexer(make_indexer: Callable[..., DocumentIndexer]) -> DocumentIndexer:
    """An indexer with the fake embedding model."""
    return make_indexer()


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point DATA_DIR to a temporary folder for the duration of the test."""
    folder = tmp_path / "atlas-data"
    monkeypatch.setenv("DATA_DIR", str(folder))
    get_settings.cache_clear()
    yield folder
    get_settings.cache_clear()


@pytest.fixture
def client(data_dir: Path, indexer: DocumentIndexer) -> Iterator[TestClient]:
    """An API client on a fresh database. The startup code runs normally,
    but uploads are indexed with the fake embedding model (no Ollama call)."""
    app.dependency_overrides[get_indexer] = lambda: indexer
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_indexer, None)