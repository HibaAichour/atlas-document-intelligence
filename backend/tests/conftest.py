"""Shared pytest fixtures."""

import hashlib
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_indexer, get_llm_provider
from app.core.config import get_settings
from app.db.session import create_db_engine, create_session_factory, init_db, sqlite_url
from app.ingestion.chunking import ChunkOptions
from app.llm.base import ChatMessage, LLMError, LLMProvider
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


@dataclass(frozen=True)
class FakeLLMCall:
    """What the code sent to the fake model in one call."""

    messages: list[ChatMessage]
    temperature: float
    json_mode: bool


class FakeLLMProvider(LLMProvider):
    """A fake text generation model for tests (no Ollama, no network).

    - replies: answers returned in order, one per call (add them in the test).
    - calls: every call received, so a test can check the prompt, or check
      that the model was not called at all.
    - unavailable: set to True to simulate a model that is down.

    A call with no reply left fails the test: an unexpected LLM call is a bug.
    """

    name = "fake"

    def __init__(self) -> None:
        self.replies: list[str] = []
        self.calls: list[FakeLLMCall] = []
        self.unavailable = False

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        json_mode: bool = False,
    ) -> str:
        self.calls.append(FakeLLMCall(list(messages), temperature, json_mode))
        if self.unavailable:
            raise LLMError("LLM request failed: connection refused")
        if not self.replies:
            raise AssertionError("FakeLLMProvider was called but has no reply left")
        return self.replies.pop(0)


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
def fake_llm() -> FakeLLMProvider:
    """A fake LLM with no scripted reply yet (the test adds them)."""
    return FakeLLMProvider()


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point DATA_DIR to a temporary folder for the duration of the test."""
    folder = tmp_path / "atlas-data"
    monkeypatch.setenv("DATA_DIR", str(folder))
    # API tests script one reply per Writer call; the Critic's model check is
    # tested on its own (test_critic.py, test_orchestrator.py).
    monkeypatch.setenv("CRITIC_USE_LLM", "false")
    get_settings.cache_clear()
    yield folder
    get_settings.cache_clear()


@pytest.fixture
def client(
    data_dir: Path, indexer: DocumentIndexer, fake_llm: FakeLLMProvider
) -> Iterator[TestClient]:
    """An API client on a fresh database. The startup code runs normally,
    but uploads are indexed with the fake embedding model and answers come
    from the fake LLM (no Ollama call)."""
    app.dependency_overrides[get_indexer] = lambda: indexer
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_indexer, None)
        app.dependency_overrides.pop(get_llm_provider, None)