"""Tests for the application settings."""

from typing import Any

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
        "RETRIEVAL_MAX_GAP",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "ollama"
    assert settings.llm_model == "qwen2.5:3b"
    assert settings.embedding_provider == "ollama"
    assert settings.embedding_model == "bge-m3"
    # Calibrated for bge-m3, whose similarity scores are lower than nomic's.
    assert settings.retrieval_min_score == 0.44
    # Only the passages near the best one reach the Writer (measured at step 11).
    assert settings.retrieval_max_gap == 0.05
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

def test_the_gap_can_be_turned_off_and_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """RETRIEVAL_MAX_GAP=1 keeps every passage above the threshold; values outside 0..1 fail."""
    no_env_file: dict[str, Any] = {"_env_file": None}  # a private option mypy does not know
    monkeypatch.setenv("RETRIEVAL_MAX_GAP", "1")
    assert Settings(**no_env_file).retrieval_max_gap == 1.0

    monkeypatch.setenv("RETRIEVAL_MAX_GAP", "-0.1")
    with pytest.raises(ValidationError):
        Settings(**no_env_file)