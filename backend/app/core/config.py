"""Application settings, loaded from environment variables and the .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
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

    # Storage: SQLite database and uploaded files (relative to the working directory)
    data_dir: Path = Path("data")


@lru_cache
def get_settings() -> Settings:
    """Return the settings, read once and then cached."""
    return Settings()