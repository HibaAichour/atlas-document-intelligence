"""The LLM provider is created at startup, and tests replace it with a fake."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_llm_provider
from app.llm.base import ChatMessage, LLMError
from app.llm.ollama import OllamaProvider
from app.main import app

QUESTION = [ChatMessage(role="user", content="Hello")]


def test_startup_creates_the_configured_llm_provider(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Environment variables win over the .env file, so the test does not
    # depend on the local configuration. No request is sent to Ollama.
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:3b")
    with TestClient(app):
        assert isinstance(app.state.llm, OllamaProvider)
        assert app.state.llm.model == "qwen2.5:3b"


def test_client_fixture_uses_the_fake_llm(client: TestClient, fake_llm) -> None:
    assert app.dependency_overrides[get_llm_provider]() is fake_llm


def test_fake_llm_returns_replies_in_order_and_records_calls(fake_llm) -> None:
    fake_llm.replies.extend(["first", "second"])

    assert fake_llm.generate(QUESTION) == "first"
    assert fake_llm.generate(QUESTION, temperature=0.2, json_mode=True) == "second"

    assert len(fake_llm.calls) == 2
    assert fake_llm.calls[0].messages == QUESTION
    assert fake_llm.calls[1].temperature == 0.2
    assert fake_llm.calls[1].json_mode is True


def test_fake_llm_can_simulate_a_model_that_is_down(fake_llm) -> None:
    fake_llm.unavailable = True

    with pytest.raises(LLMError, match="connection refused"):
        fake_llm.generate(QUESTION)
    assert len(fake_llm.calls) == 1


def test_fake_llm_fails_on_an_unexpected_call(fake_llm) -> None:
    with pytest.raises(AssertionError, match="no reply left"):
        fake_llm.generate(QUESTION)