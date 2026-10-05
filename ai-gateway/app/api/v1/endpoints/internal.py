"""Endpoints for other services, not people: authenticated with the shared internal service token
(``X-Internal-Service-Token``), not a user's access token — same scheme as assessment-service's and
subscription-service's internal APIs.

  ai-tutor-service, support-service   chat completions (the tutor and the support agent) and embeddings (RAG)
  career-service, job-portal-service  chat completions (resume tailoring, AI shortlisting) — not built yet
  ai-interview-service                transcription/speech (not built: no provider is configured)
"""

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Body, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import (
    DbSession,
    IdempotencyKeyHeader,
    ProviderRegistryDep,
    RedisDep,
    RequireInternalCaller,
    SettingsDep,
)
from app.api.responses import errors
from app.core.exceptions import ValidationFailedError
from app.providers.speech import require_stt_configured, require_tts_configured
from app.schemas.completion import CompletionIn, CompletionOut, CompletionResponse
from app.schemas.embedding import EmbeddingIn, EmbeddingOut, EmbeddingResponse
from app.services.completion_service import CompletionResult, CompletionService, TemplateVariableError
from app.services.embedding_service import EmbeddingService

router = APIRouter(prefix="/internal", tags=["Internal"], dependencies=[RequireInternalCaller])


def _template_error(exc: TemplateVariableError) -> ValidationFailedError:
    return ValidationFailedError(
        f"Missing template variable(s): {', '.join(exc.names)}.",
        code="MISSING_TEMPLATE_VARIABLE",
        details=[{"field": f"variables.{name}", "code": "REQUIRED", "message": "This field is required"} for name in exc.names],
    )


@router.post(
    "/completions",
    response_model=CompletionResponse,
    summary="Generate a chat completion",
    description="Renders `prompt_key`'s active (or pinned) version, redacts PII, checks moderation and the "
    "org's quota, then calls the routed provider (with fallback). Set `stream: true` for an "
    "`application/x-ndjson` response instead: one `{\"type\": \"delta\", \"text\": ...}` line per token, then "
    "one final `{\"type\": \"usage\", ...}` or `{\"type\": \"error\", ...}` line.",
    responses=errors(401, 403, 404, 409, 422, 429, 502, 503),
)
async def create_completion(
    body: CompletionIn, db: DbSession, settings: SettingsDep, redis: RedisDep, registry: ProviderRegistryDep, idempotency_key: IdempotencyKeyHeader
) -> CompletionResponse | StreamingResponse:
    service = CompletionService(db, settings, redis, registry)
    if not body.stream:
        try:
            result = await service.complete(
                organization_id=body.organization_id, service=body.service, user_id=body.user_id, prompt_key=body.prompt_key,
                prompt_version=body.prompt_version, variables=body.variables, messages=[m.model_dump() for m in body.messages],
                tools=body.tools, max_tokens=body.max_tokens, temperature=body.temperature, model_hint=body.model_hint,
                idempotency_key=idempotency_key,
            )
        except TemplateVariableError as exc:
            raise _template_error(exc) from exc
        return CompletionResponse(message="Completion generated.", completion=CompletionOut.model_validate(result))

    try:
        prepared = await service.prepare_stream(
            organization_id=body.organization_id, service=body.service, user_id=body.user_id, prompt_key=body.prompt_key,
            prompt_version=body.prompt_version, variables=body.variables, messages=[m.model_dump() for m in body.messages],
            tools=body.tools, max_tokens=body.max_tokens, temperature=body.temperature, model_hint=body.model_hint,
        )
    except TemplateVariableError as exc:
        raise _template_error(exc) from exc
    if isinstance(prepared, CompletionResult):
        return CompletionResponse(message="Completion generated.", completion=CompletionOut.model_validate(prepared))

    async def lines() -> AsyncIterator[bytes]:
        async for chunk in service.run_stream(prepared):
            yield (json.dumps(chunk, separators=(",", ":")) + "\n").encode()

    return StreamingResponse(lines(), media_type="application/x-ndjson")


@router.post(
    "/embeddings",
    response_model=EmbeddingResponse,
    summary="Generate embeddings",
    description="Redacts PII from every text, checks the org's quota, then calls the routed embedding provider.",
    responses=errors(401, 403, 409, 422, 429, 502, 503),
)
async def create_embeddings(
    body: EmbeddingIn, db: DbSession, settings: SettingsDep, redis: RedisDep, registry: ProviderRegistryDep, idempotency_key: IdempotencyKeyHeader
) -> EmbeddingResponse:
    result = await EmbeddingService(db, settings, redis, registry).embed(
        organization_id=body.organization_id, service=body.service, user_id=body.user_id, texts=body.texts,
        model_hint=body.model_hint, idempotency_key=idempotency_key,
    )
    return EmbeddingResponse(message="Embeddings generated.", embedding=EmbeddingOut.model_validate(result))


@router.post(
    "/transcriptions",
    summary="Speech to text (not built)",
    description="Routing contract only — see app/providers/speech.py. Answers 503 PROVIDER_NOT_CONFIGURED until a "
    "speech-to-text provider is configured; needed first by the phase-10 AI interviewer.",
    responses=errors(401, 403, 503),
)
async def create_transcription(settings: SettingsDep, audio: UploadFile) -> None:
    require_stt_configured(settings)


@router.post(
    "/speech",
    summary="Text to speech (not built)",
    description="Routing contract only — see app/providers/speech.py. Answers 503 PROVIDER_NOT_CONFIGURED until a "
    "text-to-speech provider is configured; needed first by the phase-10 AI interviewer.",
    responses=errors(401, 403, 503),
)
async def create_speech(settings: SettingsDep, text: Annotated[str, Body(embed=True, max_length=5_000)]) -> None:
    require_tts_configured(settings)
