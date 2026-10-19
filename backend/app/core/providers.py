"""Build the configured providers from the application settings."""

from pydantic import SecretStr

from app.core.config import Settings
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.llm.openai_compatible import OpenAICompatibleProvider
from app.retrieval.embeddings import (
    EmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)


def _secret(value: SecretStr | None) -> str | None:
    """Return a secret as plain text, treating an empty value as missing."""
    if value is None:
        return None
    return value.get_secret_value() or None


def build_llm_provider(settings: Settings) -> LLMProvider:
    """Create the text generation provider selected by LLM_PROVIDER."""
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            settings.llm_base_url,
            settings.llm_model,
            num_ctx=settings.llm_num_ctx,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if settings.llm_provider == "openai_compatible":
        return OpenAICompatibleProvider(
            settings.llm_base_url,
            settings.llm_model,
            api_key=_secret(settings.llm_api_key),
            timeout_seconds=settings.llm_timeout_seconds,
        )
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Create the embedding provider selected by EMBEDDING_PROVIDER."""
    if settings.embedding_provider == "ollama":
        return OllamaEmbeddingProvider(
            settings.embedding_base_url,
            settings.embedding_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if settings.embedding_provider == "openai_compatible":
        return OpenAICompatibleEmbeddingProvider(
            settings.embedding_base_url,
            settings.embedding_model,
            api_key=_secret(settings.embedding_api_key),
            timeout_seconds=settings.llm_timeout_seconds,
        )
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")