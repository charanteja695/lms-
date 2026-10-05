"""ai-gateway's internal API: chat completions (plain and streamed) and embeddings.

Authenticated with the shared internal service token, like every synchronous call between services here. The tutor
never holds a provider key or picks a model: routing, fallback, quotas, redaction and moderation are the gateway's job,
and this client only translates its answers into the four things the tutor has to decide between:
 - it worked (``Completion`` / ``Embedding``, or a ``blocked`` completion when moderation stopped the call),
 - the organization has used up its AI quota (``GatewayQuotaExceeded`` -> 429 to the student),
 - AI is switched off for the organization (``GatewayDisabled`` -> 403),
 - anything else (``GatewayUnavailable`` -> the message is saved and the student can retry).
"""

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import Settings

_QUOTA_CODES = {"QUOTA_EXCEEDED", "REQUEST_QUOTA_EXCEEDED", "TOKEN_QUOTA_EXCEEDED", "BUDGET_QUOTA_EXCEEDED"}
_DISABLED_CODES = {"ORG_SUSPENDED", "AI_DISABLED"}


class GatewayError(Exception):
    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


class GatewayQuotaExceeded(GatewayError):
    pass


class GatewayDisabled(GatewayError):
    pass


class GatewayUnavailable(GatewayError):
    """A timeout, a 5xx, or a request the gateway cannot serve (an unregistered prompt, a missing variable) — from the
    student's side all the same: the answer is not available right now."""


@dataclass(frozen=True, slots=True)
class Completion:
    call_id: int | None
    status: str  # "ok" | "blocked"
    content: str
    model: str | None
    guardrail_flags: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Embedding:
    vectors: list[list[float]]
    model: str | None


def _raise_for(response: httpx.Response) -> None:
    if response.status_code < 400:
        return
    code = None
    try:
        code = str(response.json().get("code"))
    except (ValueError, AttributeError):
        pass
    if response.status_code == 429 and code in _QUOTA_CODES:
        raise GatewayQuotaExceeded("ai-gateway quota exhausted", code=code)
    if response.status_code == 403 and code in _DISABLED_CODES:
        raise GatewayDisabled("AI is disabled for this organization", code=code)
    raise GatewayUnavailable(f"ai-gateway answered {response.status_code} {code or ''}".strip(), code=code)


def _completion(body: dict[str, Any]) -> Completion:
    c = body["completion"]
    return Completion(
        call_id=int(c["call_id"]) if c.get("call_id") else None,
        status=c["status"],
        content=c.get("content", ""),
        model=c.get("model"),
        guardrail_flags=list(c.get("guardrail_flags", [])),
    )


class GatewayClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.settings.AI_GATEWAY_URL.rstrip("/"), timeout=self.settings.AI_GATEWAY_TIMEOUT_SECONDS, transport=self._transport
        )

    def _headers(self, idempotency_key: str | None) -> dict[str, str]:
        headers = {"X-Internal-Service-Token": self.settings.INTERNAL_SERVICE_TOKEN.get_secret_value()}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _body(self, *, organization_id: int, user_id: int | None, prompt_key: str, variables: dict[str, str], messages: list[dict[str, str]], stream: bool) -> dict[str, Any]:
        return {
            "organization_id": str(organization_id),
            "service": "ai-tutor-service",
            "user_id": str(user_id) if user_id else None,
            "prompt_key": prompt_key,
            "variables": variables,
            "messages": messages,
            "max_tokens": self.settings.MAX_TOKENS,
            "stream": stream,
        }

    async def complete(
        self, *, organization_id: int, user_id: int | None, prompt_key: str, variables: dict[str, str], messages: list[dict[str, str]], idempotency_key: str | None = None
    ) -> Completion:
        body = self._body(organization_id=organization_id, user_id=user_id, prompt_key=prompt_key, variables=variables, messages=messages, stream=False)
        try:
            async with self._client() as client:
                response = await client.post("/api/v1/internal/completions", json=body, headers=self._headers(idempotency_key))
        except httpx.HTTPError as exc:
            raise GatewayUnavailable(f"ai-gateway unreachable: {exc.__class__.__name__}") from exc
        _raise_for(response)
        return _completion(response.json())

    async def stream(
        self, *, organization_id: int, user_id: int | None, prompt_key: str, variables: dict[str, str], messages: list[dict[str, str]]
    ) -> AsyncIterator[dict[str, Any]]:
        """Yields the gateway's NDJSON events (``delta`` / ``usage`` / ``error``); a moderation-blocked call, which the
        gateway answers as ordinary JSON, is yielded as one ``{"type": "blocked", ...}`` event. Raises before the first
        yield for every failure the gateway reports as an HTTP error."""
        body = self._body(organization_id=organization_id, user_id=user_id, prompt_key=prompt_key, variables=variables, messages=messages, stream=True)
        try:
            async with self._client() as client, client.stream("POST", "/api/v1/internal/completions", json=body, headers=self._headers(None)) as response:
                if response.status_code >= 400:
                    await response.aread()
                    _raise_for(response)
                if "ndjson" not in response.headers.get("content-type", ""):
                    completion = _completion(json.loads(await response.aread()))
                    yield {"type": "blocked", "call_id": completion.call_id, "guardrail_flags": completion.guardrail_flags}
                    return
                async for line in response.aiter_lines():
                    if line.strip():
                        yield json.loads(line)
        except httpx.HTTPError as exc:
            raise GatewayUnavailable(f"ai-gateway unreachable: {exc.__class__.__name__}") from exc

    async def embed(self, *, organization_id: int, user_id: int | None, texts: list[str], idempotency_key: str | None = None) -> Embedding:
        body = {"organization_id": str(organization_id), "service": "ai-tutor-service", "user_id": str(user_id) if user_id else None, "texts": texts}
        try:
            async with self._client() as client:
                response = await client.post("/api/v1/internal/embeddings", json=body, headers=self._headers(idempotency_key))
        except httpx.HTTPError as exc:
            raise GatewayUnavailable(f"ai-gateway unreachable: {exc.__class__.__name__}") from exc
        _raise_for(response)
        data = response.json()["embedding"]
        return Embedding(vectors=data["vectors"], model=data.get("model"))
