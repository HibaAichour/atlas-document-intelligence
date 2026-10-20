"""Application settings, loaded from environment variables and the .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["ollama", "openai_compatible"]


class Settings(BaseSettings):
    """All runtime configuration for the ATLAS backend.

    Each field can be overridden by an environment variable with the same
    name in upper case (for example LLM_PROVIDER or LLM_MODEL).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Text generation
    llm_provider: ProviderName = "ollama"
    llm_model: str = "qwen2.5:3b"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_api_key: SecretStr | None = None
    llm_num_ctx: int = 4096
    llm_timeout_seconds: float = 120.0

    # Embeddings
    embedding_provider: ProviderName = "ollama"
    embedding_model: str = "nomic-embed-text"
    embedding_base_url: str = "http://127.0.0.1:11434"
    embedding_api_key: SecretStr | None = None
    # Task prefixes expected by some models. nomic-embed-text was trained with
    # these two; set both to "" for a model that uses no prefix. Changing them
    # (or the model) requires re-indexing every document.
    embedding_document_prefix: str = "search_document: "
    embedding_query_prefix: str = "search_query: "
    # Number of texts sent in one embedding request.
    embedding_batch_size: int = Field(default=32, ge=1, le=512)

    # Chunking, in characters (starting values, calibrated at step 6).
    # A chunk never spans two pages; the overlap must stay below half a chunk.
    chunk_size: int = Field(default=1000, ge=100)
    chunk_overlap: int = Field(default=150, ge=0)

    # Retrieval: number of passages returned by default (the API allows 1 to 20).
    retrieval_top_k: int = Field(default=5, ge=1, le=20)

    # Storage: SQLite database and uploaded files (relative to the working directory)
    data_dir: Path = Path("data")

    # OCR (Tesseract): language pack, e.g. "eng" (must be installed with Tesseract)
    ocr_language: str = "eng"
    ocr_timeout_seconds: float = 60.0

    # Upload limits (processing is synchronous in V1, so they stay modest)
    max_upload_mb: int = 20
    max_pages: int = 50
    max_ocr_pages: int = 10


@lru_cache
def get_settings() -> Settings:
    """Return the settings, read once and then cached."""
    return Settings()