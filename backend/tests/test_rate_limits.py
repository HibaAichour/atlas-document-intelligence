"""Tests for usage limits of online providers: flagged errors, then 429 instead of 503."""

from collections.abc import Callable, Iterator
from pathlib import Path

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.api.errors import RATE_LIMIT_DETAIL, is_rate_limited, service_error
from app.core.config import get_settings
from app.llm.base import ChatMessage, LLMError
from app.llm.openai_compatible import OpenAICompatibleProvider
from app.main import app
from app.retrieval.embeddings import EmbeddingError, OpenAICompatibleEmbeddingProvider
from app.retrieval.indexing import DocumentIndexer
from app.retrieval.retriever import RetrievalError
from tests.builders import make_pdf

BASE_URL = "http://llm.test/v1"
QUESTION = "How can a party terminate the agreement?"
CONTRACT_TEXT = "Either party may terminate the agreement with 60 days written notice."
INVOICE_TEXT = "INVOICE\nInvoice No.: HDS-INV-2026-0042\nTotal due: USD 15,950.00"
GROQ_LIMIT = {"error": {"message": "Rate limit reached for model in organization org_123"}}


def mock_client(handler: Callable[[httpx2.Request], httpx2.Response]) -> httpx2.Client:
    """An HTTP client whose calls are answered by `handler`."""
    return httpx2.Client(base_url=BASE_URL, transport=httpx2.MockTransport(handler))


def answer_with(status_code: int) -> Callable[[httpx2.Request], httpx2.Response]:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status_code, json=GROQ_LIMIT)

    return handler


# --- Providers: the 429 is recorded on the error -------------------------------------


def test_llm_429_gives_a_rate_limited_error() -> None:
    provider = OpenAICompatibleProvider(BASE_URL, "model", client=mock_client(answer_with(429)))

    with pytest.raises(LLMError) as error:
        provider.generate([ChatMessage(role="user", content="Hi")])

    assert error.value.rate_limited is True
    assert "HTTP 429" in str(error.value)


@pytest.mark.parametrize("status_code", [401, 500, 503])
def test_other_llm_errors_are_not_rate_limited(status_code: int) -> None:
    provider = OpenAICompatibleProvider(
        BASE_URL, "model", client=mock_client(answer_with(status_code))
    )

    with pytest.raises(LLMError) as error:
        provider.generate([ChatMessage(role="user", content="Hi")])

    assert error.value.rate_limited is False


def test_unreachable_llm_is_not_rate_limited() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused", request=request)

    provider = OpenAICompatibleProvider(BASE_URL, "model", client=mock_client(handler))

    with pytest.raises(LLMError) as error:
        provider.generate([ChatMessage(role="user", content="Hi")])

    assert error.value.rate_limited is False


def test_embedding_429_gives_a_rate_limited_error() -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        BASE_URL, "embed-model", client=mock_client(answer_with(429))
    )

    with pytest.raises(EmbeddingError) as error:
        provider.embed(["text"])

    assert error.value.rate_limited is True


def test_other_embedding_errors_are_not_rate_limited() -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        BASE_URL, "embed-model", client=mock_client(answer_with(500))
    )

    with pytest.raises(EmbeddingError) as error:
        provider.embed(["text"])

    assert error.value.rate_limited is False


def test_errors_are_not_rate_limited_by_default() -> None:
    assert LLMError("down").rate_limited is False
    assert EmbeddingError("down").rate_limited is False


# --- service_error: 429 or 503, following the chain of causes ------------------------


def wrapped(cause: Exception) -> RetrievalError:
    """A RetrievalError raised "from" the given error, as the retriever does."""
    try:
        raise RetrievalError(f"Search failed: {cause}") from cause
    except RetrievalError as error:
        return error


def test_a_rate_limited_error_is_found_through_its_wrapper() -> None:
    assert is_rate_limited(wrapped(EmbeddingError("HTTP 429", rate_limited=True))) is True
    assert is_rate_limited(wrapped(EmbeddingError("HTTP 500"))) is False
    assert is_rate_limited(ValueError("no flag at all")) is False


def test_a_loop_of_causes_ends() -> None:
    first, second = LLMError("first"), LLMError("second")
    first.__cause__, second.__cause__ = second, first

    assert is_rate_limited(first) is False


def test_service_error_answers_429_with_a_fixed_message() -> None:
    error = service_error(LLMError("org_123 limit", rate_limited=True), "Answer generation failed")

    assert error.status_code == 429
    assert error.detail == RATE_LIMIT_DETAIL
    assert "org_123" not in error.detail


def test_service_error_answers_503_with_the_given_message() -> None:
    error = service_error(LLMError("connection refused"), "Answer generation failed: down")

    assert error.status_code == 503
    assert error.detail == "Answer generation failed: down"


# --- Routes ---------------------------------------------------------------------------


@pytest.fixture
def no_threshold(client: TestClient) -> Iterator[None]:
    """Every passage reaches the Writer, so the language model is called."""
    settings = get_settings().model_copy(update={"retrieval_min_score": 0.0})
    app.dependency_overrides[get_settings] = lambda: settings
    yield
    app.dependency_overrides.pop(get_settings, None)


def upload_pdf(client: TestClient, tmp_path: Path, filename: str, text: str) -> str:
    """Upload a one-page text PDF and return the id of the ready document."""
    path = make_pdf(tmp_path / filename, [text])
    response = client.post(
        "/api/documents", files={"file": (filename, path.read_bytes(), "application/pdf")}
    )
    assert response.json()["status"] == "ready"
    return str(response.json()["id"])


def new_session(client: TestClient) -> str:
    response = client.post("/api/sessions")
    assert response.status_code == 201
    return str(response.json()["id"])


def limit_the_model(fake_llm, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every call to the fake model fails like Groq when the limit is reached."""

    def generate(*args, **kwargs) -> str:
        raise LLMError("LLM API request failed: HTTP 429", rate_limited=True)

    monkeypatch.setattr(fake_llm, "generate", generate)


def limit_the_embeddings(indexer: DocumentIndexer, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every search question fails like Gemini when the limit is reached."""

    def embed_query(question: str) -> list[float]:
        raise EmbeddingError("Embedding request failed: HTTP 429", rate_limited=True)

    monkeypatch.setattr(indexer.embedder, "embed_query", embed_query)


def test_ask_answers_429_when_the_model_is_rate_limited(
    client: TestClient, fake_llm, no_threshold, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload_pdf(client, tmp_path, "contract.pdf", CONTRACT_TEXT)
    limit_the_model(fake_llm, monkeypatch)

    response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 429
    assert response.json()["detail"] == RATE_LIMIT_DETAIL


def test_ask_answers_429_when_the_embeddings_are_rate_limited(
    client: TestClient,
    indexer: DocumentIndexer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload_pdf(client, tmp_path, "contract.pdf", CONTRACT_TEXT)
    limit_the_embeddings(indexer, monkeypatch)

    response = client.post("/api/ask", json={"question": QUESTION})

    assert response.status_code == 429


def test_search_answers_429_when_the_embeddings_are_rate_limited(
    client: TestClient,
    indexer: DocumentIndexer,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upload_pdf(client, tmp_path, "contract.pdf", CONTRACT_TEXT)
    limit_the_embeddings(indexer, monkeypatch)

    response = client.post("/api/search", json={"query": QUESTION})

    assert response.status_code == 429
    assert response.json()["detail"] == RATE_LIMIT_DETAIL


def test_nothing_is_saved_when_a_session_question_is_rate_limited(
    client: TestClient, fake_llm, no_threshold, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upload_pdf(client, tmp_path, "contract.pdf", CONTRACT_TEXT)
    session_id = new_session(client)
    limit_the_model(fake_llm, monkeypatch)

    response = client.post(f"/api/sessions/{session_id}/ask", json={"question": QUESTION})

    assert response.status_code == 429
    body = client.get(f"/api/sessions/{session_id}").json()
    assert body["messages"] == []
    assert body["title"] is None


def test_nothing_is_saved_when_an_extraction_is_rate_limited(
    client: TestClient, fake_llm, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The Analyst falls back on keywords ("invoice"), then the Extractor hits the limit.
    document_id = upload_pdf(client, tmp_path, "invoice.pdf", INVOICE_TEXT)
    session_id = new_session(client)
    limit_the_model(fake_llm, monkeypatch)

    response = client.post(
        f"/api/sessions/{session_id}/extract", json={"document_id": document_id}
    )

    assert response.status_code == 429
    assert response.json()["detail"] == RATE_LIMIT_DETAIL
    assert client.get(f"/api/sessions/{session_id}").json()["messages"] == []