"""Tests for the Ollama provider, with the network replaced by a mock."""

import json

import httpx2
import pytest

from app.llm.base import ChatMessage, LLMError
from app.llm.ollama import OllamaProvider

BASE_URL = "http://ollama.test"


def make_provider(handler) -> OllamaProvider:
    """Build a provider whose HTTP calls are answered by `handler`."""
    client = httpx2.Client(base_url=BASE_URL, transport=httpx2.MockTransport(handler))
    return OllamaProvider(BASE_URL, "qwen2.5:3b", num_ctx=4096, client=client)


def test_generate_sends_expected_payload_and_returns_content() -> None:
    captured: dict = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"message": {"role": "assistant", "content": "Hello!"}})

    provider = make_provider(handler)
    answer = provider.generate([ChatMessage(role="user", content="Hi")])

    assert answer == "Hello!"
    assert captured["path"] == "/api/chat"
    body = captured["body"]
    assert body["model"] == "qwen2.5:3b"
    assert body["stream"] is False
    assert body["messages"] == [{"role": "user", "content": "Hi"}]
    assert body["options"] == {"temperature": 0.0, "num_ctx": 4096}
    assert "format" not in body


def test_json_mode_asks_ollama_for_json() -> None:
    captured: dict = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        captured["body"] = json.loads(request.content)
        return httpx2.Response(200, json={"message": {"content": "{}"}})

    make_provider(handler).generate([ChatMessage(role="user", content="Hi")], json_mode=True)

    assert captured["body"]["format"] == "json"


def test_server_error_raises_llm_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(500, json={"error": "model not found"})

    with pytest.raises(LLMError):
        make_provider(handler).generate([ChatMessage(role="user", content="Hi")])


def test_connection_failure_raises_llm_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("Connection refused", request=request)

    with pytest.raises(LLMError):
        make_provider(handler).generate([ChatMessage(role="user", content="Hi")])


def test_unexpected_response_shape_raises_llm_error() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, json={"unexpected": True})

    with pytest.raises(LLMError):
        make_provider(handler).generate([ChatMessage(role="user", content="Hi")])