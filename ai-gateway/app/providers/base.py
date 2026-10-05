"""Provider-agnostic request/result shapes and the two capability interfaces every provider adapter implements.
The router (app/providers/router.py) and the completion/embedding services only ever see these — never an
Anthropic- or Voyage-shaped payload directly, which is what makes a provider swappable behind ai-gateway
(docs/PRODUCT.md decision D5)."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol


class ProviderCallError(Exception):
    """The provider could not complete this call (timeout, 5xx, malformed response, ...). The router tries the
    next configured provider for this capability, if any; if none is left, the caller sees 502 PROVIDER_UNAVAILABLE."""


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass(frozen=True, slots=True)
class ChatRequest:
    model: str
    messages: list[ChatMessage]
    system: str | None = None
    max_tokens: int = 1024
    temperature: float = 0.7
    tools: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ChatResult:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    stop_reason: str | None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ChatChunk:
    """One piece of a streamed completion. ``usage`` is only set on the final chunk (``done=True``): providers
    report token counts once, at the end of the stream, not per delta."""

    delta_text: str
    done: bool = False
    stop_reason: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True, slots=True)
class EmbedRequest:
    model: str
    texts: list[str]


@dataclass(frozen=True, slots=True)
class EmbedResult:
    vectors: list[list[float]]
    model: str
    tokens: int


class ChatProvider(Protocol):
    name: str

    async def complete(self, request: ChatRequest) -> ChatResult: ...

    def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]: ...


class EmbeddingProvider(Protocol):
    name: str

    async def embed(self, request: EmbedRequest) -> EmbedResult: ...
