"""Tests for building providers from the settings."""

from app.core.config import Settings
from app.core.providers import build_embedding_provider, build_llm_provider
from app.llm.ollama import OllamaProvider
from app.llm.openai_compatible import OpenAICompatibleProvider
from app.retrieval.embeddings import (
    OllamaEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)


def make_settings(**overrides) -> Settings:
    """Settings built only from defaults and the given values (no .env file)."""
    return Settings(_env_file=None, **overrides)


def test_default_settings_build_ollama_providers() -> None:
    settings = make_settings()

    llm = build_llm_provider(settings)
    embedder = build_embedding_provider(settings)

    assert isinstance(llm, OllamaProvider)
    assert llm.model == "qwen2.5:3b"
    assert llm.num_ctx == 4096
    assert isinstance(embedder, OllamaEmbeddingProvider)
    assert embedder.model == "nomic-embed-text"


def test_openai_compatible_settings_build_hosted_providers() -> None:
    settings = make_settings(
        llm_provider="openai_compatible",
        llm_base_url="https://api.example.com/v1",
        llm_model="hosted-model",
        llm_api_key="secret-value",
        embedding_provider="openai_compatible",
        embedding_base_url="https://api.example.com/v1",
        embedding_model="hosted-embedder",
    )

    llm = build_llm_provider(settings)
    embedder = build_embedding_provider(settings)

    assert isinstance(llm, OpenAICompatibleProvider)
    assert llm.model == "hosted-model"
    assert isinstance(embedder, OpenAICompatibleEmbeddingProvider)
    assert embedder.model == "hosted-embedder"


def test_empty_api_key_is_treated_as_missing() -> None:
    settings = make_settings(llm_provider="openai_compatible", llm_api_key="")

    llm = build_llm_provider(settings)

    assert isinstance(llm, OpenAICompatibleProvider)
    assert llm._headers == {}