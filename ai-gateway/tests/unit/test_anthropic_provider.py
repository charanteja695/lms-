"""Exercises AnthropicProvider against httpx's mock transport, verifying it speaks the documented Messages API
shape correctly — not exercised against the real network (see app/providers/anthropic.py's docstring)."""

import json

import httpx
import pytest

from app.core.config import Settings
from app.providers.anthropic import AnthropicProvider
from app.providers.base import ChatMessage, ChatRequest, ProviderCallError


def _settings() -> Settings:
    return Settings(ANTHROPIC_API_KEY="sk-ant-test", ANTHROPIC_BASE_URL="https://api.anthropic.test")


def _request() -> ChatRequest:
    return ChatRequest(model="claude-sonnet-5-5", messages=[ChatMessage(role="user", content="Hi")], system="Be terse.", max_tokens=100)


def _provider(handler) -> AnthropicProvider:
    return AnthropicProvider(_settings(), transport=httpx.MockTransport(handler))


async def test_complete_parses_text_and_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-sonnet-5-5",
                "content": [{"type": "text", "text": "Hello there!"}], "stop_reason": "end_turn",
                "usage": {"input_tokens": 12, "output_tokens": 4},
            },
        )

    result = await _provider(handler).complete(_request())
    assert result.content == "Hello there!"
    assert result.prompt_tokens == 12 and result.completion_tokens == 4
    assert result.stop_reason == "end_turn"


async def test_complete_sends_the_documented_request_shape() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}], "model": "claude-sonnet-5-5", "usage": {"input_tokens": 1, "output_tokens": 1}})

    await _provider(handler).complete(_request())
    sent = captured[0]
    assert sent.headers["x-api-key"] == "sk-ant-test"
    assert sent.headers["anthropic-version"]
    body = json.loads(sent.content)
    assert body["model"] == "claude-sonnet-5-5" and body["system"] == "Be terse." and body["stream"] is False
    assert body["messages"] == [{"role": "user", "content": "Hi"}]


async def test_tool_use_blocks_are_returned_separately_from_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "Let me check."}, {"type": "tool_use", "id": "tu_1", "name": "lookup_status", "input": {"attempt_id": "1"}}],
                "model": "claude-sonnet-5-5", "usage": {"input_tokens": 5, "output_tokens": 5},
            },
        )

    result = await _provider(handler).complete(_request())
    assert result.content == "Let me check."
    assert result.tool_calls == [{"type": "tool_use", "id": "tu_1", "name": "lookup_status", "input": {"attempt_id": "1"}}]


async def test_a_5xx_response_raises_provider_call_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(529, text="overloaded")

    with pytest.raises(ProviderCallError):
        await _provider(handler).complete(_request())


async def test_a_network_error_raises_provider_call_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(ProviderCallError):
        await _provider(handler).complete(_request())


def _sse(*events: dict) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events).encode()


async def test_stream_yields_text_deltas_then_a_final_usage_chunk() -> None:
    body = _sse(
        {"type": "message_start", "message": {"usage": {"input_tokens": 8}}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "Hel"}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "lo"}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 3}},
        {"type": "message_stop"},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    chunks = [c async for c in _provider(handler).stream(_request())]
    assert [c.delta_text for c in chunks if not c.done] == ["Hel", "lo"]
    final = chunks[-1]
    assert final.done and final.stop_reason == "end_turn" and final.prompt_tokens == 8 and final.completion_tokens == 3


async def test_stream_raises_provider_call_error_on_an_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="bad key")

    with pytest.raises(ProviderCallError):
        async for _ in _provider(handler).stream(_request()):
            pass
