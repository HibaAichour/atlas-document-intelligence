"""Text generation with a local Ollama server."""

from typing import Any

import httpx2

from app.core.http_errors import describe_http_error
from app.llm.base import ChatMessage, LLMError, LLMProvider


class OllamaProvider(LLMProvider):
    """Calls the native Ollama chat API (POST /api/chat)."""

    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        num_ctx: int = 4096,
        timeout_seconds: float = 120.0,
        client: httpx2.Client | None = None,
    ) -> None:
        self.model = model
        self.num_ctx = num_ctx
        # A client can be injected, which lets tests replace the network.
        self._client = client or httpx2.Client(
            base_url=base_url.rstrip("/"), timeout=timeout_seconds
        )

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        json_mode: bool = False,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature, "num_ctx": self.num_ctx},
        }
        if json_mode:
            payload["format"] = "json"

        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx2.HTTPError as exc:
            raise LLMError(f"Ollama request failed: {describe_http_error(exc)}") from exc
        except ValueError as exc:
            raise LLMError("Ollama returned a response that is not valid JSON") from exc

        try:
            return str(data["message"]["content"])
        except (KeyError, TypeError) as exc:
            raise LLMError("Unexpected response format from Ollama") from exc