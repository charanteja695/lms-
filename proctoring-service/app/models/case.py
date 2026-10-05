import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import AppealStatus, CaseStatus


class IntegrityCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The integrity decision on one attempt (docs/PRODUCT.md §5.3). Low risk is cleared automatically (a closed case
    with ``decision = clear`` and no reviewer, kept for the audit trail); anything else waits here for a person. A human
    always confirms an invalidation, and the student can appeal it once, to a *different* reviewer."""

    __tablename__ = "integrity_cases"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proctor_sessions.id", ondelete="CASCADE"))
    session_public_id: Mapped[int] = mapped_column(BigInteger)
    attempt_id: Mapped[int] = mapped_column(BigInteger)
    test_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    test_owner_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(12), default=CaseStatus.OPEN, server_default=CaseStatus.OPEN)
    severity: Mapped[str] = mapped_column(String(8))
    risk_score: Mapped[int] = mapped_column(Integer)
    report: Mapped[dict[str, Any]] = mapped_column(JSONType)  # the integrity report, frozen when the case was opened
    reasons: Mapped[list[str]] = mapped_column(JSONType)  # why a human is needed, in words

    assigned_to: Mapped[int | None] = mapped_column(BigInteger)
    decision: Mapped[str | None] = mapped_column(String(12))
    decided_by: Mapped[int | None] = mapped_column(BigInteger)  # None: decided automatically
    decided_at: Mapped[datetime | None]
    decision_note: Mapped[str | None] = mapped_column(Text)

    appeal_status: Mapped[str] = mapped_column(String(12), default=AppealStatus.NONE, server_default=AppealStatus.NONE)
    appeal_reason: Mapped[str | None] = mapped_column(Text)
    appealed_at: Mapped[datetime | None]
    appeal_decided_by: Mapped[int | None] = mapped_column(BigInteger)
    appeal_decided_at: Mapped[datetime | None]
    appeal_note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("session_id", name="uq_integrity_cases_session"),
        Index("ix_integrity_cases_status_created", "status", "created_at"),
        Index("ix_integrity_cases_test", "test_id", "status"),
        Index("ix_integrity_cases_org", "organization_id", "status"),
        Index("ix_integrity_cases_attempt", "attempt_id"),
    )
