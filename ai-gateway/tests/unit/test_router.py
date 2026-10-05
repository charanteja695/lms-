"""app/providers/router.py: provider selection and fallback, against fake providers (no HTTP at all)."""

import pytest

from app.core.exceptions import ProviderNotConfiguredError, ProviderUnavailableError
from app.providers.base import ChatChunk, ChatMessage, ChatResult, EmbedResult, ProviderCallError
from app.providers.registry import ProviderRegistry
from app.providers.router import ProviderRouter, RouteEntry


class _Boom:
    name = "boom"

    async def complete(self, request):
        raise ProviderCallError("down")

    async def stream(self, request):
        raise ProviderCallError("down")
        yield  # pragma: no cover - makes this an async generator function


class _Ok:
    name = "ok"

    async def complete(self, request):
        return ChatResult(content="fine", model=request.model, prompt_tokens=1, completion_tokens=1, stop_reason="end_turn")

    async def stream(self, request):
        yield ChatChunk(delta_text="fine", done=True, prompt_tokens=1, completion_tokens=1, stop_reason="end_turn")


async def test_complete_uses_the_first_provider_when_it_succeeds() -> None:
    registry = ProviderRegistry.for_testing(chat={"ok": _Ok()})
    router = ProviderRouter(registry, [RouteEntry("ok", "model-a")])
    result, provider = await router.complete(system=None, messages=[ChatMessage(role="user", content="hi")], max_tokens=10, temperature=0.5, tools=[])
    assert provider == "ok" and result.content == "fine"


async def test_complete_falls_back_to_the_next_provider_on_failure() -> None:
    registry = ProviderRegistry.for_testing(chat={"boom": _Boom(), "ok": _Ok()})
    router = ProviderRouter(registry, [RouteEntry("boom", "model-a"), RouteEntry("ok", "model-b")])
    result, provider = await router.complete(system=None, messages=[ChatMessage(role="user", content="hi")], max_tokens=10, temperature=0.5, tools=[])
    assert provider == "ok" and result.content == "fine"


async def test_complete_raises_provider_unavailable_when_every_provider_fails() -> None:
    registry = ProviderRegistry.for_testing(chat={"boom": _Boom()})
    router = ProviderRouter(registry, [RouteEntry("boom", "model-a")])
    with pytest.raises(ProviderUnavailableError):
        await router.complete(system=None, messages=[ChatMessage(role="user", content="hi")], max_tokens=10, temperature=0.5, tools=[])


async def test_complete_raises_provider_not_configured_with_an_empty_route() -> None:
    registry = ProviderRegistry.for_testing()
    router = ProviderRouter(registry, [])
    with pytest.raises(ProviderNotConfiguredError):
        await router.complete(system=None, messages=[ChatMessage(role="user", content="hi")], max_tokens=10, temperature=0.5, tools=[])


async def test_complete_skips_a_route_entry_whose_provider_was_never_registered() -> None:
    """A route can name a provider that has no API key configured; the router treats it like a failure and moves on."""
    registry = ProviderRegistry.for_testing(chat={"ok": _Ok()})
    router = ProviderRouter(registry, [RouteEntry("not-registered", "model-a"), RouteEntry("ok", "model-b")])
    result, provider = await router.complete(system=None, messages=[ChatMessage(role="user", content="hi")], max_tokens=10, temperature=0.5, tools=[])
    assert provider == "ok"


async def test_stream_falls_back_when_the_first_provider_fails_before_any_chunk() -> None:
    registry = ProviderRegistry.for_testing(chat={"boom": _Boom(), "ok": _Ok()})
    router = ProviderRouter(registry, [RouteEntry("boom", "model-a"), RouteEntry("ok", "model-b")])
    chunks, provider = await router.stream(system=None, messages=[ChatMessage(role="user", content="hi")], max_tokens=10, temperature=0.5, tools=[])
    collected = [c async for c in chunks]
    assert provider == "ok" and collected[0].delta_text == "fine"


async def test_stream_raises_when_every_provider_fails() -> None:
    registry = ProviderRegistry.for_testing(chat={"boom": _Boom()})
    router = ProviderRouter(registry, [RouteEntry("boom", "model-a")])
    with pytest.raises(ProviderUnavailableError):
        await router.stream(system=None, messages=[ChatMessage(role="user", content="hi")], max_tokens=10, temperature=0.5, tools=[])


async def test_embed_falls_back_on_failure() -> None:
    class _BoomEmbed:
        name = "boom"

        async def embed(self, request):
            raise ProviderCallError("down")

    class _OkEmbed:
        name = "ok"

        async def embed(self, request):
            return EmbedResult(vectors=[[0.1]], model=request.model, tokens=5)

    registry = ProviderRegistry.for_testing(embedding={"boom": _BoomEmbed(), "ok": _OkEmbed()})
    router = ProviderRouter(registry, [RouteEntry("boom", "model-a"), RouteEntry("ok", "model-b")])
    result, provider = await router.embed(texts=["hi"])
    assert provider == "ok" and result.tokens == 5
