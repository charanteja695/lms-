"""The audit/eval log: one row per call, whatever its outcome (docs/PRODUCT.md §6: "eval logs").

``request_redacted`` and ``response_preview`` hold only what was actually sent to (and received from) the
provider *after* redaction — see app/guardrails/redact.py. Raw, unredacted content is never written to this
table. Pruned by the worker after ``CALL_LOG_RETENTION_DAYS``.
"""

from typing import Any

from sqlalchemy import BigInteger, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import CallStatus


class AiCallLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "ai_call_logs"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    organization_id: Mapped[int] = mapped_column(BigInteger)
    service: Mapped[str] = mapped_column(String(60))  # the calling service, e.g. "ai-tutor-service"
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    capability: Mapped[str] = mapped_column(String(20))
    prompt_key: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[int | None] = mapped_column(Integer)
    provider: Mapped[str | None] = mapped_column(String(30))
    model: Mapped[str | None] = mapped_column(String(60))
    request_redacted: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    response_preview: Mapped[str | None] = mapped_column(String(2000))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=CallStatus.OK)
    error_code: Mapped[str | None] = mapped_column(String(60))
    guardrail_flags: Mapped[list[str]] = mapped_column(JSONType, default=list)
    idempotency_key: Mapped[str | None] = mapped_column(String(80))

    __table_args__ = (
        Index("ix_ai_call_logs_org_created", "organization_id", "created_at"),
        Index("ix_ai_call_logs_service_created", "service", "created_at"),
    )
