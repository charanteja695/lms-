"""ai-gateway's internal API: chat completions.

Authenticated with the shared internal service token, like every synchronous call between services here. This service
never holds a provider key or picks a model: routing, fallback, quotas, redaction and moderation are the gateway's job,
and this client only translates its answers into the things the resume builder has to decide between:
 - it worked (``Completion`` / ``Embedding``, or a ``blocked`` completion when moderation stopped the call),
 - the organization has used up its AI quota (``GatewayQuotaExceeded`` -> 429),
 - AI is switched off for the organization (``GatewayDisabled`` -> 403),
 - anything else (``GatewayUnavailable`` -> 503, the student can retry).
"""

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


class SpeechUnavailable(GatewayError):
    """Speech-to-text or text-to-speech is not available (ai-gateway answers 503 PROVIDER_NOT_CONFIGURED until a provider is wired). Text always works."""


class GatewayUnavailable(GatewayError):
    """A timeout, a 5xx, or a request the gateway cannot serve (an unregistered prompt, a missing variable) — from the
    student's side all the same: the answer is not available right now."""


@dataclass(frozen=True, slots=True)
class Embedding:
    vectors: list[list[float]]
    model: str | None


@dataclass(frozen=True, slots=True)
class Completion:
    call_id: int | None
    status: str  # "ok" | "blocked"
    content: str
    model: str | None
    guardrail_flags: list[str] = field(default_factory=list)
    prompt_version: int | None = None


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
        prompt_version=c.get("prompt_version"),
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

    def _body(self, *, organization_id: int, user_id: int | None, prompt_key: str, variables: dict[str, str], messages: list[dict[str, str]], stream: bool, max_tokens: int | None = None) -> dict[str, Any]:
        return {
            "organization_id": str(organization_id),
            "service": "ai-interview-service",
            "user_id": str(user_id) if user_id else None,
            "prompt_key": prompt_key,
            "variables": variables,
            "messages": messages,
            "max_tokens": max_tokens or self.settings.MAX_TOKENS,
            "stream": stream,
        }

    async def complete(
        self, *, organization_id: int, user_id: int | None, prompt_key: str, variables: dict[str, str], messages: list[dict[str, str]], idempotency_key: str | None = None,
        max_tokens: int | None = None,
    ) -> Completion:
        body = self._body(organization_id=organization_id, user_id=user_id, prompt_key=prompt_key, variables=variables, messages=messages, stream=False, max_tokens=max_tokens)
        try:
            async with self._client() as client:
                response = await client.post("/api/v1/internal/completions", json=body, headers=self._headers(idempotency_key))
        except httpx.HTTPError as exc:
            raise GatewayUnavailable(f"ai-gateway unreachable: {exc.__class__.__name__}") from exc
        _raise_for(response)
        return _completion(response.json())

    async def embed(self, *, organization_id: int, user_id: int | None, texts: list[str], idempotency_key: str | None = None) -> Embedding:
        body = {"organization_id": str(organization_id), "service": "ai-interview-service", "user_id": str(user_id) if user_id else None, "texts": texts}
        try:
            async with self._client() as client:
                response = await client.post("/api/v1/internal/embeddings", json=body, headers=self._headers(idempotency_key))
        except httpx.HTTPError as exc:
            raise GatewayUnavailable(f"ai-gateway unreachable: {exc.__class__.__name__}") from exc
        _raise_for(response)
        data = response.json()["embedding"]
        return Embedding(vectors=data["vectors"], model=data.get("model"))

    async def transcribe(self, audio: bytes, *, content_type: str, organization_id: int, user_id: int) -> str:
        """Speech to text through ai-gateway's ``POST /internal/transcriptions`` (multipart ``audio``). The gateway's route is a contract only, so this
        is written to that contract — ``{"transcription": {"text": ...}}`` — and any refusal is ``SpeechUnavailable``: the candidate types instead."""
        try:
            async with self._client() as client:
                response = await client.post(
                    "/api/v1/internal/transcriptions", files={"audio": ("answer", audio, content_type)}, data={"organization_id": str(organization_id), "user_id": str(user_id)},
                    headers=self._headers(None),
                )
        except httpx.HTTPError as exc:
            raise SpeechUnavailable(f"ai-gateway unreachable: {exc.__class__.__name__}") from exc
        if response.status_code >= 400:
            raise SpeechUnavailable(f"speech-to-text answered {response.status_code}")
        try:
            return str(response.json()["transcription"]["text"]).strip()
        except (ValueError, KeyError, TypeError) as exc:
            raise SpeechUnavailable("speech-to-text answered in an unexpected shape") from exc

    async def synthesize(self, text: str, *, organization_id: int, user_id: int) -> tuple[bytes, str]:
        """Text to speech through ``POST /internal/speech``: the audio bytes and their content type. Contract only, like ``transcribe``."""
        try:
            async with self._client() as client:
                response = await client.post(
                    "/api/v1/internal/speech", json={"text": text, "organization_id": str(organization_id), "user_id": str(user_id)}, headers=self._headers(None)
                )
        except httpx.HTTPError as exc:
            raise SpeechUnavailable(f"ai-gateway unreachable: {exc.__class__.__name__}") from exc
        if response.status_code >= 400 or not response.content:
            raise SpeechUnavailable(f"text-to-speech answered {response.status_code}")
        return response.content, response.headers.get("content-type", "audio/mpeg")
