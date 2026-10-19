"""Tests for the OpenAI-compatible provider, with the network replaced by a mock."""

import json

import httpx2
import pytest

from app.llm.base import ChatMessage, LLMError
from app.llm.openai_compatible import OpenAICompatibleProvider

# A base URL with a path prefix, like Groq's https://api.groq.com/openai/v1
BASE_URL = "http://llm.test/openai/v1"


def make_provider(handler, api_key: str | None = "test-key") -> OpenAICompatibleProvider:
    """Build a provider whose HTTP calls are answered by `handler`."""
    client = httpx2.Client(base_url=BASE_URL, transport=httpx2.MockTransport(handler))
    return OpenAICompatibleProvider(BASE_URL, "test-model", api_key=api_key, client=client)


def ok_response(content: str | None = "Hello!") -> httpx2.Response:
    """A minimal successful chat completion response."""
    return httpx2.Response(
        200, json={"choices": [{"message": {"role": "assistant", "content": content}}]}
    )


def test_generate_sends_expected_request_and_returns_content() -> None:
    captured: dict = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content)
        return ok_response()

    answer = make_provider(handler).generate([ChatMessage(role="user", content="Hi")])

    assert answer == "Hello!"
    assert captured["path"] == "/openai/v1/chat/completions"
    assert captured["auth"] == "Bearer test-key"
    body = captured["body"]
    assert body["model"] == "test-model"
    assert body["messages"] == [{"role": "user", "content": "Hi"}]
    assert body["temperature"] == 0.0
    assert "response_format" not in body


def test_no_api_key_sends_no_authorization_header() -> None:
    captured: dict = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["auth"] = request.headers.get("Authorization")
        return ok_response()

    make_provider(handler, api_key=None).generate([ChatMessage(role="user", content="Hi")])

    assert captured["auth"] is None


def test_json_mode_requests_a_json_object() -> None:
    captured: dict = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["body"] = json.loads(request.content)
        return ok_response("{}")

    make_provider(handler).generate([ChatMessage(role="user", content="Hi")], json_mode=True)

    assert captured["body"]["response_format"] == {"type": "json_object"}


def test_authentication_error_raises_llm_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(401, json={"error": {"message": "Invalid API key"}})

    with pytest.raises(LLMError):
        make_provider(handler).generate([ChatMessage(role="user", content="Hi")])


def test_empty_choices_raise_llm_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"choices": []})

    with pytest.raises(LLMError):
        make_provider(handler).generate([ChatMessage(role="user", content="Hi")])


def test_null_content_raises_llm_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return ok_response(content=None)

    with pytest.raises(LLMError):
        make_provider(handler).generate([ChatMessage(role="user", content="Hi")])