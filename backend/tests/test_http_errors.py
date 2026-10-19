"""Tests for readable HTTP error messages."""

import httpx2
import pytest

from app.llm.base import ChatMessage, LLMError
from app.llm.openai_compatible import OpenAICompatibleProvider

BASE_URL = "http://llm.test/v1"


def test_error_message_includes_the_reason_given_by_the_server() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            404, json={"error": {"message": "The model `old-model` does not exist"}}
        )

    client = httpx2.Client(base_url=BASE_URL, transport=httpx2.MockTransport(handler))
    provider = OpenAICompatibleProvider(BASE_URL, "old-model", client=client)

    with pytest.raises(LLMError) as error:
        provider.generate([ChatMessage(role="user", content="Hi")])

    message = str(error.value)
    assert "HTTP 404" in message
    assert "does not exist" in message