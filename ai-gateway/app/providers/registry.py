"""Builds the configured provider adapters once per process. A provider whose API key is unset is left out of the
registry entirely — the router then reports PROVIDER_NOT_CONFIGURED for a capability with nothing left to try,
rather than calling out with an empty key and getting a confusing 401 from the provider itself.
"""

from functools import lru_cache

import httpx

from app.core.config import Settings, get_settings
from app.domain.enums import ProviderName
from app.providers.anthropic import AnthropicProvider
from app.providers.base import ChatProvider, EmbeddingProvider
from app.providers.voyage import VoyageProvider


class ProviderRegistry:
    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._chat: dict[str, ChatProvider] = {}
        self._embedding: dict[str, EmbeddingProvider] = {}
        if settings.ANTHROPIC_API_KEY is not None:
            self._chat[ProviderName.ANTHROPIC] = AnthropicProvider(settings, transport)
        if settings.VOYAGE_API_KEY is not None:
            self._embedding[ProviderName.VOYAGE] = VoyageProvider(settings, transport)

    @classmethod
    def for_testing(cls, *, chat: dict[str, ChatProvider] | None = None, embedding: dict[str, EmbeddingProvider] | None = None) -> "ProviderRegistry":
        """A registry wired to test doubles instead of real HTTP clients, bypassing Settings entirely —
        used by tests that exercise CompletionService/EmbeddingService without an HTTP layer at all."""
        registry = cls.__new__(cls)
        registry._chat = chat or {}
        registry._embedding = embedding or {}
        return registry

    def chat(self, name: str) -> ChatProvider | None:
        return self._chat.get(name)

    def embedding(self, name: str) -> EmbeddingProvider | None:
        return self._embedding.get(name)


@lru_cache
def _cached() -> ProviderRegistry:
    return ProviderRegistry(get_settings())


def get_registry(settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None) -> ProviderRegistry:
    """The cached, process-wide registry for real use; pass ``transport`` (tests only) to bypass the cache and
    get a fresh registry wired to a mock transport instead."""
    if transport is not None:
        return ProviderRegistry(settings, transport=transport)
    return _cached()
