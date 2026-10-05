"""Writes and queries the audit/eval log (app/models/call_log.py)."""

from typing import Any

from lms_common.pagination import paginate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_public_id
from app.models.call_log import AiCallLog


class CallLogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def record(
        self,
        *,
        organization_id: int,
        service: str,
        user_id: int | None,
        capability: str,
        prompt_key: str | None,
        prompt_version: int | None,
        provider: str | None,
        model: str | None,
        request_redacted: dict[str, Any],
        response_preview: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        cost_cents: int,
        latency_ms: int,
        status: str,
        error_code: str | None = None,
        guardrail_flags: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> AiCallLog:
        log = AiCallLog(
            public_id=new_public_id(),
            organization_id=organization_id,
            service=service,
            user_id=user_id,
            capability=capability,
            prompt_key=prompt_key,
            prompt_version=prompt_version,
            provider=provider,
            model=model,
            request_redacted=request_redacted,
            response_preview=response_preview[:2000] if response_preview else None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_cents=cost_cents,
            latency_ms=latency_ms,
            status=status,
            error_code=error_code,
            guardrail_flags=guardrail_flags or [],
            idempotency_key=idempotency_key,
        )
        self.db.add(log)
        return log

    async def list_logs(
        self,
        *,
        organization_id: int | None,
        service: str | None,
        prompt_key: str | None,
        status: str | None,
        page: int,
        per_page: int,
    ) -> tuple[list[AiCallLog], int, bool]:
        stmt = select(AiCallLog).order_by(AiCallLog.created_at.desc(), AiCallLog.id)
        if organization_id is not None:
            stmt = stmt.where(AiCallLog.organization_id == organization_id)
        if service is not None:
            stmt = stmt.where(AiCallLog.service == service)
        if prompt_key is not None:
            stmt = stmt.where(AiCallLog.prompt_key == prompt_key)
        if status is not None:
            stmt = stmt.where(AiCallLog.status == status)
        return await paginate(self.db, stmt, page, per_page)
