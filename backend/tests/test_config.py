"""Tests for the application settings."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults_run_locally_with_ollama(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without any configuration, ATLAS targets the local Ollama models."""
    for name in (
        "LLM_PROVIDER",
        "LLM_MODEL",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL",
        "RETRIEVAL_MIN_SCORE",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "ollama"
    assert settings.llm_model == "qwen2.5:3b"
    assert settings.embedding_provider == "ollama"
    assert settings.embedding_model == "bge-m3"
    # Calibrated for bge-m3, whose similarity scores are lower than nomic's.
    assert settings.retrieval_min_score == 0.44
    assert settings.llm_api_key is None


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables take precedence over default values."""
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_MODEL", "some-model")
    monkeypatch.setenv("LLM_API_KEY", "secret-value")

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "openai_compatible"
    assert settings.llm_model == "some-model"
    assert settings.llm_api_key is not None
    assert settings.llm_api_key.get_secret_value() == "secret-value"
    # The key must never appear in plain text when settings are printed.
    assert "secret-value" not in str(settings)


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A typo in the provider name stops the application at startup."""
    monkeypatch.setenv("LLM_PROVIDER", "olama")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)