"""Build the configured providers from the application settings."""

from pydantic import SecretStr

from app.core.config import Settings
from app.ingestion.chunking import ChunkOptions
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.llm.openai_compatible import OpenAICompatibleProvider
from app.retrieval.embedder import Embedder
from app.retrieval.embeddings import (
    EmbeddingProvider,
    OllamaEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)
from app.retrieval.indexing import DocumentIndexer
from app.retrieval.vector_store import ChromaVectorStore

CHROMA_FOLDER = "chroma"


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


def build_document_indexer(settings: Settings) -> DocumentIndexer:
    """Create the indexer: embedding provider, vector store and chunking options.

    Nothing is sent to the embedding service here, so the server starts even
    when Ollama is not running. The vector store lives in DATA_DIR/chroma.
    """
    embedder = Embedder.from_settings(build_embedding_provider(settings), settings)
    vector_store = ChromaVectorStore(settings.data_dir / CHROMA_FOLDER, settings.embedding_model)
    chunk_options = ChunkOptions(
        chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
    )
    return DocumentIndexer(embedder, vector_store, chunk_options)