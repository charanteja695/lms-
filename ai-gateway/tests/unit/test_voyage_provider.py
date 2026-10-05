import json

import httpx
import pytest

from app.core.config import Settings
from app.providers.base import EmbedRequest, ProviderCallError
from app.providers.voyage import VoyageProvider


def _settings() -> Settings:
    return Settings(VOYAGE_API_KEY="voyage-test", VOYAGE_BASE_URL="https://api.voyage.test")


def _provider(handler) -> VoyageProvider:
    return VoyageProvider(_settings(), transport=httpx.MockTransport(handler))


async def test_embed_returns_vectors_in_request_order_even_if_the_provider_reorders_them() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "object": "list", "model": "voyage-3",
                "data": [{"object": "embedding", "embedding": [0.9, 0.9], "index": 1}, {"object": "embedding", "embedding": [0.1, 0.1], "index": 0}],
                "usage": {"total_tokens": 20},
            },
        )

    result = await _provider(handler).embed(EmbedRequest(model="voyage-3", texts=["first", "second"]))
    assert result.vectors == [[0.1, 0.1], [0.9, 0.9]]
    assert result.tokens == 20


async def test_embed_sends_the_documented_request_shape() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, json={"data": [{"embedding": [0.0], "index": 0}], "model": "voyage-3", "usage": {"total_tokens": 3}})

    await _provider(handler).embed(EmbedRequest(model="voyage-3", texts=["hello"]))
    sent = captured[0]
    assert sent.headers["authorization"] == "Bearer voyage-test"
    body = json.loads(sent.content)
    assert body == {"model": "voyage-3", "input": ["hello"]}


async def test_a_5xx_response_raises_provider_call_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="try later")

    with pytest.raises(ProviderCallError):
        await _provider(handler).embed(EmbedRequest(model="voyage-3", texts=["hi"]))
