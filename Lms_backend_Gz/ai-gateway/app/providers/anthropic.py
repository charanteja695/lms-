"""Real client for Anthropic's Messages API (the primary chat provider — docs/PRODUCT.md decision D5).

Written against the well-documented Messages API shape (POST /v1/messages, SSE streaming with
``message_start`` / ``content_block_delta`` / ``message_delta`` / ``message_stop`` events). Like the rest of
this service's outbound integrations (Judge0, the proctoring AI analyzer), it is **not exercised against the
real network** in this environment — tests mock the HTTP layer with respx. Verify against a live key before
relying on it in an environment that has one.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import Settings
from app.providers.base import ChatChunk, ChatProvider, ChatRequest, ChatResult, ProviderCallError


def _content_blocks(message: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for block in message.get("content", []):
        if block.get("type") == "text":
            text_parts.append(str(block.get("text", "")))
        elif block.get("type") == "tool_use":
            tool_calls.append(block)
    return "".join(text_parts), tool_calls


class AnthropicProvider(ChatProvider):
    name = "anthropic"

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        api_key = self.settings.ANTHROPIC_API_KEY
        return httpx.AsyncClient(
            base_url=self.settings.ANTHROPIC_BASE_URL.rstrip("/"),
            timeout=self.settings.ANTHROPIC_TIMEOUT_SECONDS,
            transport=self._transport,
            headers={
                "x-api-key": api_key.get_secret_value() if api_key else "",
                "anthropic-version": self.settings.ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
        )

    def _body(self, request: ChatRequest, *, stream: bool) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "stream": stream,
        }
        if request.system:
            body["system"] = request.system
        if request.tools:
            body["tools"] = request.tools
        return body

    async def complete(self, request: ChatRequest) -> ChatResult:
        try:
            async with self._client() as client:
                response = await client.post("/v1/messages", json=self._body(request, stream=False))
        except httpx.HTTPError as exc:
            raise ProviderCallError(f"anthropic unreachable: {exc.__class__.__name__}") from exc
        if response.status_code >= 400:
            raise ProviderCallError(f"anthropic answered {response.status_code}: {response.text[:280]}")
        data = response.json()
        text, tool_calls = _content_blocks(data)
        usage = data.get("usage", {})
        return ChatResult(
            content=text,
            model=data.get("model", request.model),
            prompt_tokens=int(usage.get("input_tokens", 0)),
            completion_tokens=int(usage.get("output_tokens", 0)),
            stop_reason=data.get("stop_reason"),
            tool_calls=tool_calls,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        prompt_tokens = 0
        completion_tokens = 0
        stop_reason: str | None = None
        try:
            async with self._client() as client, client.stream("POST", "/v1/messages", json=self._body(request, stream=True)) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise ProviderCallError(f"anthropic answered {response.status_code}: {body[:280].decode(errors='replace')}")
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line.removeprefix("data:").strip()
                    if not payload:
                        continue
                    event = json.loads(payload)
                    event_type = event.get("type")
                    if event_type == "message_start":
                        prompt_tokens = int(event.get("message", {}).get("usage", {}).get("input_tokens", 0))
                    elif event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield ChatChunk(delta_text=delta.get("text", ""))
                    elif event_type == "message_delta":
                        stop_reason = event.get("delta", {}).get("stop_reason") or stop_reason
                        completion_tokens = int(event.get("usage", {}).get("output_tokens", completion_tokens))
                    elif event_type == "message_stop":
                        yield ChatChunk(delta_text="", done=True, stop_reason=stop_reason, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
                        return
        except httpx.HTTPError as exc:
            raise ProviderCallError(f"anthropic unreachable: {exc.__class__.__name__}") from exc
        # The stream ended without a message_stop event (a truncated connection): still tell the caller how much
        # was generated, rather than silently reporting zero usage for tokens that were, in fact, produced.
        yield ChatChunk(delta_text="", done=True, stop_reason=stop_reason, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
