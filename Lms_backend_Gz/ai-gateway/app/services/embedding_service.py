"""Embeddings: redact, check quota, call the embedding provider (with fallback), log and settle — the same shape
as app/services/completion_service.py but with no prompt registry (there is no system prompt to render or
tools to allow-list) and no moderation (indexed course content and student questions are not generative output).
Token cost is estimated with a coarse heuristic (about 4 characters per token) before the call and reconciled
with the provider's own count afterwards, the same reserve-then-adjust shape quotas use for chat.
"""

import time
from dataclasses import asdict, dataclass, field

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import PermissionDeniedError, ProviderNotConfiguredError, ProviderUnavailableError
from app.core.time import utcnow
from app.domain.enums import CallStatus, Capability
from app.guardrails.redact import redact_text
from app.models.refs import OrgStatusRef
from app.providers.pricing import embedding_cost_cents
from app.providers.registry import ProviderRegistry
from app.providers.router import ProviderRouter
from app.services.call_log_service import CallLogService
from app.services.idempotency_service import IdempotencyCache, request_hash
from app.services.model_route_service import ModelRouteService
from app.services.outbox import write_event
from app.services.quota_service import QuotaService

IDEMPOTENCY_SCOPE = "embedding"
_CHARS_PER_TOKEN = 4


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    call_id: str
    vectors: list[list[float]] = field(default_factory=list)
    model: str | None = None
    provider: str | None = None
    tokens: int = 0
    cost_cents: int = 0


class EmbeddingService:
    def __init__(self, db: AsyncSession, settings: Settings, redis: Redis, registry: ProviderRegistry) -> None:
        self.db = db
        self.settings = settings
        self.redis = redis
        self.registry = registry

    async def embed(
        self, *, organization_id: int, service: str, user_id: int | None, texts: list[str], model_hint: str | None, idempotency_key: str | None
    ) -> EmbeddingResult:
        payload_for_hash = {"organization_id": organization_id, "texts": texts, "model_hint": model_hint}
        cache = IdempotencyCache(self.redis, self.settings)
        if idempotency_key:
            cached = await cache.find(organization_id, IDEMPOTENCY_SCOPE, idempotency_key, request_hash(payload_for_hash))
            if cached is not None:
                return EmbeddingResult(**cached)

        redacted = [redact_text(t) for t in texts]
        redacted_texts = [r.text for r in redacted]
        flags = sorted({flag for r in redacted for flag in r.flags})

        org = await self.db.get(OrgStatusRef, organization_id)
        if org is not None and org.suspended:
            raise PermissionDeniedError("AI usage is disabled while this organization is suspended.", code="ORG_SUSPENDED")

        estimated_tokens = sum(max(1, len(t) // _CHARS_PER_TOKEN) for t in redacted_texts)
        quota = QuotaService(self.db, self.settings)
        reservation = await quota.reserve(organization_id=organization_id, estimated_tokens=estimated_tokens)

        route = await ModelRouteService(self.db, self.settings).resolve(Capability.EMBEDDING)
        await self.db.commit()  # close the read-only transaction the resolve() call opened (see the note in completion_service.complete())

        router = ProviderRouter(self.registry, route)
        started = time.perf_counter()
        try:
            result, provider_name = await router.embed(texts=redacted_texts, model_hint=model_hint)
        except (ProviderUnavailableError, ProviderNotConfiguredError) as exc:
            await quota.refund(reservation)
            CallLogService(self.db).record(
                organization_id=organization_id, service=service, user_id=user_id, capability=Capability.EMBEDDING,
                prompt_key=None, prompt_version=None, provider=None, model=model_hint,
                request_redacted={"texts": redacted_texts}, response_preview=None, prompt_tokens=0, completion_tokens=0,
                cost_cents=0, latency_ms=int((time.perf_counter() - started) * 1000), status=CallStatus.ERROR,
                error_code=exc.code, guardrail_flags=flags, idempotency_key=idempotency_key,
            )
            await self.db.commit()
            raise

        latency_ms = int((time.perf_counter() - started) * 1000)
        cost_cents = embedding_cost_cents(result.model, tokens=result.tokens)
        await quota.adjust(reservation, prompt_tokens=result.tokens, completion_tokens=0, cost_cents=cost_cents)

        log = CallLogService(self.db).record(
            organization_id=organization_id, service=service, user_id=user_id, capability=Capability.EMBEDDING,
            prompt_key=None, prompt_version=None, provider=provider_name, model=result.model,
            request_redacted={"texts": redacted_texts}, response_preview=f"{len(result.vectors)} vector(s)",
            prompt_tokens=result.tokens, completion_tokens=0, cost_cents=cost_cents, latency_ms=latency_ms,
            status=CallStatus.OK, guardrail_flags=flags, idempotency_key=idempotency_key,
        )
        await self.db.flush()  # log.id (a client-side default) is only populated once flushed; write_event needs it
        write_event(
            self.db, event_type="ai.usage", aggregate_type="ai_call_log", aggregate_id=log.id,
            payload={
                "organization_id": str(organization_id), "service": service, "user_id": str(user_id) if user_id else None,
                "capability": Capability.EMBEDDING.value, "provider": provider_name, "model": result.model, "prompt_key": None,
                "prompt_tokens": result.tokens, "completion_tokens": 0, "cost_cents": cost_cents,
                "status": CallStatus.OK.value, "call_id": str(log.public_id), "occurred_at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        await self.db.commit()

        embedding = EmbeddingResult(call_id=str(log.public_id), vectors=result.vectors, model=result.model, provider=provider_name, tokens=result.tokens, cost_cents=cost_cents)
        if idempotency_key:
            await cache.remember(organization_id, IDEMPOTENCY_SCOPE, idempotency_key, request_hash(payload_for_hash), asdict(embedding))
        return embedding
