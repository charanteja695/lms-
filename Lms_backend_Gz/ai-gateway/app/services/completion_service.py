"""Orchestrates one chat completion end to end: resolve the registered prompt, redact, moderate, check the org is
allowed to spend, reserve quota, call a provider (falling back per app/providers/router.py), log the call and
settle the quota reservation against what actually happened.

Order matters and is deliberate:

1. idempotency replay (skips everything below on a hit)
2. tool allow-list (a caller error — cheap to reject before touching anything else)
3. render the prompt template
4. redact PII — *before* moderation, so a blocked phrase hidden inside what would have been redacted still
   can't slip through, and before anything is logged
5. moderate the redacted text — blocked calls cost nothing and never reach a provider
6. org enabled/suspended
7. reserve quota (commits — nothing slow has happened yet)
8. call the provider (outside any open transaction)
9. adjust the reservation and write the audit log (a fresh transaction; see app/services/quota_service.py)
"""

import time
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass, field
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import PermissionDeniedError, ProviderNotConfiguredError, ProviderUnavailableError
from app.core.time import utcnow
from app.domain.enums import CallStatus, Capability
from app.guardrails.moderation import moderate
from app.guardrails.redact import redact_messages, redact_text
from app.guardrails.tools import check_tools_allowed
from app.models.refs import OrgStatusRef
from app.prompt.render import MissingVariables, render
from app.providers.base import ChatMessage
from app.providers.pricing import chat_cost_cents
from app.providers.registry import ProviderRegistry
from app.providers.router import ProviderRouter, RouteEntry
from app.services.call_log_service import CallLogService
from app.services.idempotency_service import IdempotencyCache, request_hash
from app.services.model_route_service import ModelRouteService
from app.services.outbox import write_event
from app.services.prompt_service import PromptService
from app.services.quota_service import QuotaService, Reservation

IDEMPOTENCY_SCOPE = "completion"


@dataclass(frozen=True, slots=True)
class CompletionResult:
    call_id: str
    status: str
    content: str
    model: str | None
    provider: str | None
    prompt_tokens: int
    completion_tokens: int
    cost_cents: int
    guardrail_flags: list[str] = field(default_factory=list)
    stop_reason: str | None = None
    prompt_version: int | None = None  # the registry version that was rendered: callers that log decisions for audit record it


@dataclass(frozen=True, slots=True)
class StreamContext:
    """Everything a stream needs, already reserved and ready — built by ``prepare_stream`` (which can still fail
    with a normal error, or answer "blocked", *before* any HTTP streaming response has started), then handed to
    ``run_stream`` (which only ever does the slow part: call the provider and yield)."""

    organization_id: int
    service: str
    user_id: int | None
    prompt_key: str
    prompt_version: int
    system_text: str
    messages: list[ChatMessage]
    tools: list[dict[str, Any]]
    max_tokens: int
    temperature: float
    model_hint: str | None
    guardrail_flags: list[str]
    route: list[RouteEntry]
    reservation: Reservation


class TemplateVariableError(Exception):
    def __init__(self, names: tuple[str, ...]) -> None:
        self.names = names


async def _org_suspended(db: AsyncSession, organization_id: int) -> bool:
    ref = await db.get(OrgStatusRef, organization_id)
    return ref is not None and ref.suspended


class CompletionService:
    def __init__(self, db: AsyncSession, settings: Settings, redis: Redis, registry: ProviderRegistry) -> None:
        self.db = db
        self.settings = settings
        self.redis = redis
        self.registry = registry

    async def complete(
        self,
        *,
        organization_id: int,
        service: str,
        user_id: int | None,
        prompt_key: str,
        prompt_version: int | None,
        variables: dict[str, str],
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        max_tokens: int | None,
        temperature: float | None,
        model_hint: str | None,
        idempotency_key: str | None,
    ) -> CompletionResult:
        prompts = PromptService(self.db)
        prompt = await prompts.get_prompt(prompt_key)
        version = await prompts.get_version(prompt, prompt_version) if prompt_version else await prompts.active_version(prompt)

        payload_for_hash = {
            "organization_id": organization_id, "prompt_key": prompt_key, "version": version.version,
            "variables": variables, "messages": messages, "tools": tools, "max_tokens": max_tokens, "temperature": temperature,
        }
        cache = IdempotencyCache(self.redis, self.settings)
        if idempotency_key:
            cached = await cache.find(organization_id, IDEMPOTENCY_SCOPE, idempotency_key, request_hash(payload_for_hash))
            if cached is not None:
                return CompletionResult(**cached)

        check_tools_allowed(tools, version.allowed_tools)

        try:
            system_text = render(version.template, variables)
        except MissingVariables as exc:
            raise TemplateVariableError(exc.names) from exc

        redacted_system = redact_text(system_text)
        redacted_messages, message_flags = redact_messages(messages)
        flags = redacted_system.flags | message_flags

        blocked = moderate(redacted_system.text, self.settings.MODERATION_BLOCKLIST)
        for msg in redacted_messages:
            blocked += moderate(msg["content"], self.settings.MODERATION_BLOCKLIST)
        if blocked:
            flags.add("moderation")
            log = CallLogService(self.db).record(
                organization_id=organization_id, service=service, user_id=user_id, capability=Capability.CHAT,
                prompt_key=prompt_key, prompt_version=version.version, provider=None, model=None,
                request_redacted={"system": redacted_system.text, "messages": redacted_messages},
                response_preview=None, prompt_tokens=0, completion_tokens=0, cost_cents=0, latency_ms=0,
                status=CallStatus.BLOCKED, error_code="MODERATION_BLOCKED", guardrail_flags=sorted(flags),
                idempotency_key=idempotency_key,
            )
            await self.db.commit()
            return CompletionResult(
                call_id=str(log.public_id), status=CallStatus.BLOCKED, content="", model=None, provider=None,
                prompt_tokens=0, completion_tokens=0, cost_cents=0, guardrail_flags=sorted(flags), prompt_version=version.version,
            )

        if await _org_suspended(self.db, organization_id):
            raise PermissionDeniedError("AI usage is disabled while this organization is suspended.", code="ORG_SUSPENDED")

        max_tokens = min(max_tokens or int(version.model_params.get("max_tokens", 1024)), self.settings.MAX_TOKENS_PER_CALL)
        temperature = temperature if temperature is not None else float(version.model_params.get("temperature", self.settings.DEFAULT_TEMPERATURE))

        quota = QuotaService(self.db, self.settings)
        reservation = await quota.reserve(organization_id=organization_id, estimated_tokens=max_tokens)

        route = await ModelRouteService(self.db, self.settings).resolve(Capability.CHAT)
        # Close the read-only transaction the resolve() call opened, before the slow provider call. commit(), not
        # rollback(): with expire_on_commit=False this ends the transaction without expiring `version`/`prompt`,
        # which are still read below (rollback() always expires loaded objects, regardless of that setting, and
        # a bare attribute access on an expired object outside an awaited call raises MissingGreenlet).
        await self.db.commit()

        router = ProviderRouter(self.registry, route)
        chat_messages = [ChatMessage(role=m["role"], content=m["content"]) for m in redacted_messages]
        started = time.perf_counter()
        try:
            result, provider_name = await router.complete(
                system=redacted_system.text, messages=chat_messages, max_tokens=max_tokens, temperature=temperature, tools=tools, model_hint=model_hint
            )
        except (ProviderUnavailableError, ProviderNotConfiguredError) as exc:
            await quota.refund(reservation)
            CallLogService(self.db).record(
                organization_id=organization_id, service=service, user_id=user_id, capability=Capability.CHAT,
                prompt_key=prompt_key, prompt_version=version.version, provider=None, model=model_hint,
                request_redacted={"system": redacted_system.text, "messages": redacted_messages},
                response_preview=None, prompt_tokens=0, completion_tokens=0, cost_cents=0,
                latency_ms=int((time.perf_counter() - started) * 1000), status=CallStatus.ERROR,
                error_code=exc.code, guardrail_flags=sorted(flags), idempotency_key=idempotency_key,
            )
            await self.db.commit()
            raise

        latency_ms = int((time.perf_counter() - started) * 1000)
        cost_cents = chat_cost_cents(result.model, prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens)
        await quota.adjust(reservation, prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens, cost_cents=cost_cents)

        log = CallLogService(self.db).record(
            organization_id=organization_id, service=service, user_id=user_id, capability=Capability.CHAT,
            prompt_key=prompt_key, prompt_version=version.version, provider=provider_name, model=result.model,
            request_redacted={"system": redacted_system.text, "messages": redacted_messages},
            response_preview=result.content, prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens,
            cost_cents=cost_cents, latency_ms=latency_ms, status=CallStatus.OK, guardrail_flags=sorted(flags),
            idempotency_key=idempotency_key,
        )
        await self.db.flush()  # log.id (a client-side default) is only populated once flushed; write_event needs it
        write_event(
            self.db, event_type="ai.usage", aggregate_type="ai_call_log", aggregate_id=log.id,
            payload={
                "organization_id": str(organization_id), "service": service, "user_id": str(user_id) if user_id else None,
                "capability": Capability.CHAT.value, "provider": provider_name, "model": result.model, "prompt_key": prompt_key,
                "prompt_tokens": result.prompt_tokens, "completion_tokens": result.completion_tokens, "cost_cents": cost_cents,
                "status": CallStatus.OK.value, "call_id": str(log.public_id), "occurred_at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        await self.db.commit()

        completion = CompletionResult(
            call_id=str(log.public_id), status=CallStatus.OK, content=result.content, model=result.model, provider=provider_name,
            prompt_tokens=result.prompt_tokens, completion_tokens=result.completion_tokens, cost_cents=cost_cents,
            guardrail_flags=sorted(flags), stop_reason=result.stop_reason, prompt_version=version.version,
        )
        if idempotency_key:
            await cache.remember(organization_id, IDEMPOTENCY_SCOPE, idempotency_key, request_hash(payload_for_hash), asdict(completion))
        return completion

    async def prepare_stream(
        self,
        *,
        organization_id: int,
        service: str,
        user_id: int | None,
        prompt_key: str,
        prompt_version: int | None,
        variables: dict[str, str],
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        max_tokens: int | None,
        temperature: float | None,
        model_hint: str | None,
    ) -> StreamContext | CompletionResult:
        """No ``idempotency_key``: a live stream is not something a retry can sensibly replay from cache. Returns
        a ``CompletionResult`` directly (never starts a stream) when the call is blocked; everything else this
        raises is the same set of errors ``complete()`` raises, for the same reasons — see the class docstring."""
        prompts = PromptService(self.db)
        prompt = await prompts.get_prompt(prompt_key)
        version = await prompts.get_version(prompt, prompt_version) if prompt_version else await prompts.active_version(prompt)

        check_tools_allowed(tools, version.allowed_tools)
        try:
            system_text = render(version.template, variables)
        except MissingVariables as exc:
            raise TemplateVariableError(exc.names) from exc

        redacted_system = redact_text(system_text)
        redacted_messages, message_flags = redact_messages(messages)
        flags = redacted_system.flags | message_flags

        blocked = moderate(redacted_system.text, self.settings.MODERATION_BLOCKLIST)
        for msg in redacted_messages:
            blocked += moderate(msg["content"], self.settings.MODERATION_BLOCKLIST)
        if blocked:
            flags.add("moderation")
            log = CallLogService(self.db).record(
                organization_id=organization_id, service=service, user_id=user_id, capability=Capability.CHAT,
                prompt_key=prompt_key, prompt_version=version.version, provider=None, model=None,
                request_redacted={"system": redacted_system.text, "messages": redacted_messages},
                response_preview=None, prompt_tokens=0, completion_tokens=0, cost_cents=0, latency_ms=0,
                status=CallStatus.BLOCKED, error_code="MODERATION_BLOCKED", guardrail_flags=sorted(flags), idempotency_key=None,
            )
            await self.db.commit()
            return CompletionResult(
                call_id=str(log.public_id), status=CallStatus.BLOCKED, content="", model=None, provider=None,
                prompt_tokens=0, completion_tokens=0, cost_cents=0, guardrail_flags=sorted(flags), prompt_version=version.version,
            )

        if await _org_suspended(self.db, organization_id):
            raise PermissionDeniedError("AI usage is disabled while this organization is suspended.", code="ORG_SUSPENDED")

        resolved_max_tokens = min(max_tokens or int(version.model_params.get("max_tokens", 1024)), self.settings.MAX_TOKENS_PER_CALL)
        resolved_temperature = temperature if temperature is not None else float(version.model_params.get("temperature", self.settings.DEFAULT_TEMPERATURE))

        quota = QuotaService(self.db, self.settings)
        reservation = await quota.reserve(organization_id=organization_id, estimated_tokens=resolved_max_tokens)
        route = await ModelRouteService(self.db, self.settings).resolve(Capability.CHAT)
        await self.db.commit()  # close the read-only transaction before the streaming HTTP response starts (see the note in complete())

        return StreamContext(
            organization_id=organization_id, service=service, user_id=user_id, prompt_key=prompt_key, prompt_version=version.version,
            system_text=redacted_system.text, messages=[ChatMessage(role=m["role"], content=m["content"]) for m in redacted_messages],
            tools=tools, max_tokens=resolved_max_tokens, temperature=resolved_temperature, model_hint=model_hint,
            guardrail_flags=sorted(flags), route=route, reservation=reservation,
        )

    async def run_stream(self, ctx: StreamContext) -> AsyncIterator[dict[str, Any]]:
        """Yields ``{"type": "delta", "text": ...}`` chunks, then exactly one final ``{"type": "usage", ...}`` or
        ``{"type": "error", "code": ...}`` item. Settles the quota reservation and writes the audit log itself —
        there is no "after the endpoint returns" step for a streaming response, so this is where that lives."""
        quota = QuotaService(self.db, self.settings)
        router = ProviderRouter(self.registry, ctx.route)
        started = time.perf_counter()
        text_parts: list[str] = []
        try:
            chunks, provider_name = await router.stream(
                system=ctx.system_text, messages=ctx.messages, max_tokens=ctx.max_tokens, temperature=ctx.temperature, tools=ctx.tools, model_hint=ctx.model_hint
            )
            usage_prompt_tokens = usage_completion_tokens = 0
            stop_reason: str | None = None
            async for chunk in chunks:
                if chunk.delta_text:
                    text_parts.append(chunk.delta_text)
                    yield {"type": "delta", "text": chunk.delta_text}
                if chunk.done:
                    usage_prompt_tokens, usage_completion_tokens, stop_reason = chunk.prompt_tokens, chunk.completion_tokens, chunk.stop_reason
        except (ProviderUnavailableError, ProviderNotConfiguredError) as exc:
            await quota.refund(ctx.reservation)
            CallLogService(self.db).record(
                organization_id=ctx.organization_id, service=ctx.service, user_id=ctx.user_id, capability=Capability.CHAT,
                prompt_key=ctx.prompt_key, prompt_version=ctx.prompt_version, provider=None, model=ctx.model_hint,
                request_redacted={"system": ctx.system_text, "messages": [{"role": m.role, "content": m.content} for m in ctx.messages]},
                response_preview="".join(text_parts) or None, prompt_tokens=0, completion_tokens=0, cost_cents=0,
                latency_ms=int((time.perf_counter() - started) * 1000), status=CallStatus.ERROR, error_code=exc.code,
                guardrail_flags=ctx.guardrail_flags, idempotency_key=None,
            )
            await self.db.commit()
            yield {"type": "error", "code": exc.code, "message": exc.message}
            return

        model = ctx.model_hint or (ctx.route[0].model if ctx.route else "")
        cost_cents = chat_cost_cents(model, prompt_tokens=usage_prompt_tokens, completion_tokens=usage_completion_tokens)
        await quota.adjust(ctx.reservation, prompt_tokens=usage_prompt_tokens, completion_tokens=usage_completion_tokens, cost_cents=cost_cents)
        log = CallLogService(self.db).record(
            organization_id=ctx.organization_id, service=ctx.service, user_id=ctx.user_id, capability=Capability.CHAT,
            prompt_key=ctx.prompt_key, prompt_version=ctx.prompt_version, provider=provider_name, model=model,
            request_redacted={"system": ctx.system_text, "messages": [{"role": m.role, "content": m.content} for m in ctx.messages]},
            response_preview="".join(text_parts), prompt_tokens=usage_prompt_tokens, completion_tokens=usage_completion_tokens,
            cost_cents=cost_cents, latency_ms=int((time.perf_counter() - started) * 1000), status=CallStatus.OK,
            guardrail_flags=ctx.guardrail_flags, idempotency_key=None,
        )
        await self.db.flush()  # log.id (a client-side default) is only populated once flushed; write_event needs it
        write_event(
            self.db, event_type="ai.usage", aggregate_type="ai_call_log", aggregate_id=log.id,
            payload={
                "organization_id": str(ctx.organization_id), "service": ctx.service, "user_id": str(ctx.user_id) if ctx.user_id else None,
                "capability": Capability.CHAT.value, "provider": provider_name, "model": model, "prompt_key": ctx.prompt_key,
                "prompt_tokens": usage_prompt_tokens, "completion_tokens": usage_completion_tokens, "cost_cents": cost_cents,
                "status": CallStatus.OK.value, "call_id": str(log.public_id), "occurred_at": utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        await self.db.commit()
        yield {
            "type": "usage", "call_id": str(log.public_id), "provider": provider_name, "model": model, "prompt_tokens": usage_prompt_tokens,
            "completion_tokens": usage_completion_tokens, "cost_cents": cost_cents, "stop_reason": stop_reason,
        }
