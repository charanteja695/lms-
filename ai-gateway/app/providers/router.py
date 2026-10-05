"""Picks a provider for a capability and falls back on failure (docs/PRODUCT.md §6: "provider routing" and
decision D5: "Claude as primary model, with provider fallback").

Routing order comes from ``ModelRoute`` (app/models/model_route.py) when a row exists, else a single-entry
default built from ``Settings``. Every entry is tried in order for a non-streaming call; for a streaming call,
only failures *before the first chunk* fall back — once output has reached the caller, switching providers
mid-stream would mean silently splicing two different completions together, which is worse than just failing.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.core.exceptions import ProviderNotConfiguredError, ProviderUnavailableError
from app.domain.enums import Capability, ProviderName
from app.providers.base import ChatChunk, ChatRequest, ChatResult, EmbedRequest, EmbedResult, ProviderCallError
from app.providers.registry import ProviderRegistry


@dataclass(frozen=True, slots=True)
class RouteEntry:
    provider: str
    model: str


def default_route(settings: Settings, capability: str) -> list[RouteEntry]:
    if capability == Capability.CHAT:
        return [RouteEntry(ProviderName.ANTHROPIC, settings.ANTHROPIC_DEFAULT_MODEL)]
    if capability == Capability.EMBEDDING:
        return [RouteEntry(ProviderName.VOYAGE, settings.VOYAGE_DEFAULT_MODEL)]
    return []


def route_from_config(rows: list[dict[str, Any]]) -> list[RouteEntry]:
    return [RouteEntry(str(row["provider"]), str(row["model"])) for row in rows]


class ProviderRouter:
    def __init__(self, registry: ProviderRegistry, route: list[RouteEntry]) -> None:
        self.registry = registry
        self.route = route

    async def complete(self, *, system: str | None, messages: list[Any], max_tokens: int, temperature: float, tools: list[dict[str, Any]], model_hint: str | None = None) -> tuple[ChatResult, str]:
        if not self.route:
            raise ProviderNotConfiguredError("No chat provider is configured.")
        errors: list[str] = []
        for entry in self.route:
            provider = self.registry.chat(entry.provider)
            if provider is None:
                errors.append(f"{entry.provider}: not configured")
                continue
            request = ChatRequest(
                model=model_hint or entry.model, messages=messages, system=system, max_tokens=max_tokens, temperature=temperature, tools=tools
            )
            try:
                return await provider.complete(request), entry.provider
            except ProviderCallError as exc:
                errors.append(f"{entry.provider}: {exc}")
        raise ProviderUnavailableError(f"Every configured chat provider failed: {'; '.join(errors)}")

    async def stream(self, *, system: str | None, messages: list[Any], max_tokens: int, temperature: float, tools: list[dict[str, Any]], model_hint: str | None = None) -> tuple[AsyncIterator[ChatChunk], str]:
        if not self.route:
            raise ProviderNotConfiguredError("No chat provider is configured.")
        errors: list[str] = []
        for entry in self.route:
            provider = self.registry.chat(entry.provider)
            if provider is None:
                errors.append(f"{entry.provider}: not configured")
                continue
            request = ChatRequest(
                model=model_hint or entry.model, messages=messages, system=system, max_tokens=max_tokens, temperature=temperature, tools=tools
            )
            try:
                first_chunk, rest = await _peek(provider.stream(request))
            except ProviderCallError as exc:
                errors.append(f"{entry.provider}: {exc}")
                continue
            return _prepend(first_chunk, rest), entry.provider
        raise ProviderUnavailableError(f"Every configured chat provider failed: {'; '.join(errors)}")

    async def embed(self, *, texts: list[str], model_hint: str | None = None) -> tuple[EmbedResult, str]:
        if not self.route:
            raise ProviderNotConfiguredError("No embedding provider is configured.")
        errors: list[str] = []
        for entry in self.route:
            provider = self.registry.embedding(entry.provider)
            if provider is None:
                errors.append(f"{entry.provider}: not configured")
                continue
            try:
                return await provider.embed(EmbedRequest(model=model_hint or entry.model, texts=texts)), entry.provider
            except ProviderCallError as exc:
                errors.append(f"{entry.provider}: {exc}")
        raise ProviderUnavailableError(f"Every configured embedding provider failed: {'; '.join(errors)}")


async def _peek(stream: AsyncIterator[ChatChunk]) -> tuple[ChatChunk, AsyncIterator[ChatChunk]]:
    """Pull the first chunk out so a connection failure on it can still fall back to the next provider,
    before committing the caller to this one."""
    first = await anext(stream)
    return first, stream


async def _prepend(first: ChatChunk, rest: AsyncIterator[ChatChunk]) -> AsyncIterator[ChatChunk]:
    yield first
    async for chunk in rest:
        yield chunk
