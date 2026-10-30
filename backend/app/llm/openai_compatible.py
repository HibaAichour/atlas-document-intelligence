"""Text generation with any OpenAI-compatible chat API (Groq, Ollama /v1, ...)."""

from typing import Any

import httpx2

from app.core.http_errors import describe_http_error, is_too_many_requests
from app.llm.base import ChatMessage, LLMError, LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    """Calls POST {base_url}/chat/completions with the OpenAI request format."""

    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
        client: httpx2.Client | None = None,
    ) -> None:
        self.model = model
        # Local servers such as Ollama need no key; hosted APIs do.
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
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
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = self._client.post("/chat/completions", json=payload, headers=self._headers)
            response.raise_for_status()
            data = response.json()
        except httpx2.HTTPError as exc:
            raise LLMError(
                f"LLM API request failed: {describe_http_error(exc)}",
                rate_limited=is_too_many_requests(exc),
            ) from exc
        except ValueError as exc:
            raise LLMError("LLM API returned a response that is not valid JSON") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unexpected response format from the LLM API") from exc
        if content is None:
            raise LLMError("The LLM API returned an empty message")
        return str(content)