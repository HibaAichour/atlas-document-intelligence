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
    # bge-m3 (multilingual, chosen at step 10 bis with scripts/probe_embeddings.py):
    # a French question finds an English passage and the other way round.
    embedding_model: str = "bge-m3"
    embedding_base_url: str = "http://127.0.0.1:11434"
    embedding_api_key: SecretStr | None = None
    # Task prefixes expected by some models. bge-m3 uses none; nomic-embed-text
    # needs "search_document: " and "search_query: ". Changing them (or the
    # model) requires re-indexing every document.
    embedding_document_prefix: str = ""
    embedding_query_prefix: str = ""
    # Number of texts sent in one embedding request.
    embedding_batch_size: int = Field(default=32, ge=1, le=512)

    # Chunking, in characters (starting values, calibrated at step 6).
    # A chunk never spans two pages; the overlap must stay below half a chunk.
    chunk_size: int = Field(default=1000, ge=100)
    chunk_overlap: int = Field(default=150, ge=0)

    # Retrieval: number of passages returned by default (the API allows 1 to 20).
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    # Relevance threshold (cosine similarity). A question whose passages all
    # score below it is refused without calling the LLM, and only passages at
    # or above it are given to the Writer. Measured at step 10 bis on the four
    # demo documents with bge-m3, in English, French and across both: the
    # passages that answer a question (top 5) scored 0.464 or more, off-topic
    # questions 0.262 to 0.409. Absent but related questions (0.46 to 0.64)
    # pass and are refused by the Writer (NOT_FOUND). The threshold depends on
    # the model: recalibrate with "python -m scripts.probe_scores" whenever
    # the embedding model changes (nomic-embed-text used 0.6).
    retrieval_min_score: float = Field(default=0.44, ge=0.0, le=1.0)
    # Gap to the best score: only the passages above the threshold AND within
    # this distance of the best one are given to the Writer. With bge-m3 the
    # scores are close, so the threshold alone lets the whole top 5 through.
    # Measured at step 11 (python -m scripts.probe_margin): with 0.05, no right
    # passage is lost on the 53 questions of probe_scores, the Writer gets 2.9
    # passages instead of 4.9 on average, its answers are unchanged on 11
    # questions and arrive about 2.5 times faster. 0.03 lost a table passage.
    # Set it to 1 to keep every passage above the threshold.
    retrieval_max_gap: float = Field(default=0.05, ge=0.0, le=1.0)

    # Critic: besides its code checks (citations, numbers), it asks the model
    # which sentences no passage supports. That costs about 3 to 5 s more per
    # answer with qwen2.5:3b; set CRITIC_USE_LLM=false to keep the code checks only.
    critic_use_llm: bool = True

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