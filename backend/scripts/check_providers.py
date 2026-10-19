"""Manual check: call the configured LLM and embedding providers for real.

Run from the backend folder, with the virtual environment active:

    python -m scripts.check_providers

The providers are chosen by the environment variables and the .env file,
exactly as in the application.
"""

import sys
import time

from app.core.config import Settings
from app.core.providers import build_embedding_provider, build_llm_provider
from app.llm.base import ChatMessage, LLMError
from app.retrieval.embeddings import EmbeddingError


def main() -> int:
    """Run both checks and return a process exit code (0 means success)."""
    settings = Settings()
    print(f"LLM:        {settings.llm_provider} | {settings.llm_model} | {settings.llm_base_url}")
    print(
        f"Embeddings: {settings.embedding_provider} | {settings.embedding_model} "
        f"| {settings.embedding_base_url}"
    )

    llm = build_llm_provider(settings)
    start = time.perf_counter()
    try:
        answer = llm.generate(
            [
                ChatMessage(role="system", content="Answer in one short sentence."),
                ChatMessage(role="user", content="What is retrieval-augmented generation?"),
            ]
        )
    except LLMError as exc:
        print(f"\n[FAIL] LLM: {exc}")
        return 1
    print(f"\n[OK] LLM answered in {time.perf_counter() - start:.1f}s:\n     {answer.strip()}")

    embedder = build_embedding_provider(settings)
    start = time.perf_counter()
    try:
        vectors = embedder.embed(["ATLAS answers questions about documents."])
    except EmbeddingError as exc:
        print(f"\n[FAIL] Embeddings: {exc}")
        return 1
    print(
        f"\n[OK] Embeddings returned a vector of {len(vectors[0])} dimensions "
        f"in {time.perf_counter() - start:.1f}s"
    )

    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())