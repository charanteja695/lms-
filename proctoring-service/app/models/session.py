import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import AnalysisStatus, SessionStatus


class TestRef(TimestampMixin, Base):
    """From assessment-service's ``test.published`` / ``test.retired``: which tests are proctored, at what level, and who
    owns them (an employer's hiring assessment, or the platform). A pure read-model."""

    __tablename__ = "test_refs"
    __test__ = False

    test_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(10))
    proctoring_level: Mapped[str] = mapped_column(String(10))
    owner_organization_id: Mapped[int | None] = mapped_column(BigInteger)
    retired: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


class ProctorSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One student's monitored sitting of one test, from the pre-check to the integrity decision."""

    __tablename__ = "proctor_sessions"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    test_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)  # the student's institution
    test_owner_id: Mapped[int | None] = mapped_column(BigInteger)  # an employer's hiring assessment, else None
    attempt_id: Mapped[int | None] = mapped_column(BigInteger)  # assessment-service's attempt, once it starts
    level: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(12), default=SessionStatus.PRECHECK, server_default=SessionStatus.PRECHECK)

    consent_at: Mapped[datetime | None]
    consent_version: Mapped[str | None] = mapped_column(String(20))
    precheck: Mapped[dict[str, Any] | None] = mapped_column(JSONType)  # what the system check reported
    device_fingerprint: Mapped[str | None] = mapped_column(String(128))
    ip_address: Mapped[str | None] = mapped_column(String(45))  # the last seen
    user_agent: Mapped[str | None] = mapped_column(String(500))

    started_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]
    last_heartbeat_at: Mapped[datetime | None]
    heartbeat_lost: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # inside a gap right now
    terminated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # The live risk: points per event type (each capped by app/risk/policy.py), and their capped sum.
    risk_breakdown: Mapped[dict[str, int]] = mapped_column(JSONType)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    critical: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # a finding that needs a human
    flag_emitted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # integrity.flagged sent
    snapshot_seq: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # periodic snapshots so far

    finalize_due_at: Mapped[datetime | None]

    __table_args__ = (
        Index("ix_proctor_sessions_user_test", "user_id", "test_id", "created_at"),
        Index("ix_proctor_sessions_attempt", "attempt_id"),
        Index("ix_proctor_sessions_test_status", "test_id", "status"),
        Index("ix_proctor_sessions_org_status", "organization_id", "status"),
        Index(
            "ix_proctor_sessions_live",
            "last_heartbeat_at",
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        Index(
            "ix_proctor_sessions_finalize",
            "finalize_due_at",
            postgresql_where=text("status = 'submitted'"),
            sqlite_where=text("status = 'submitted'"),
        ),
    )


class ProctorEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One thing that happened in a session (the timeline of the integrity report). High volume: it is append-only and
    indexed by session and time so it can be range-partitioned by ``occurred_at`` when it reaches billions of rows."""

    __tablename__ = "proctor_events"

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proctor_sessions.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(8))
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow)
    points: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # what it added to the risk score
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)  # staff who did it

    __table_args__ = (Index("ix_proctor_events_session_time", "session_id", "occurred_at"),)


class Snapshot(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Metadata of an image or audio clip the browser uploaded straight to object storage. The bytes never pass through
    this service; access to them is audited and they are deleted after ``MEDIA_RETENTION_DAYS``."""

    __tablename__ = "snapshots"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proctor_sessions.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(12))
    sequence: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # periodic snapshots: 1, 2, 3...
    s3_key: Mapped[str | None] = mapped_column(String(300))
    taken_at: Mapped[datetime]
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    analysis_status: Mapped[str] = mapped_column(String(10), default=AnalysisStatus.PENDING, server_default=AnalysisStatus.PENDING)
    analysis_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    analysis_available_at: Mapped[datetime] = mapped_column(default=utcnow)
    findings: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    skip_reason: Mapped[str | None] = mapped_column(String(80))
    delete_after: Mapped[datetime]
    deleted_at: Mapped[datetime | None]

    __table_args__ = (
        Index("ix_snapshots_session_taken", "session_id", "taken_at"),
        Index(
            "ix_snapshots_analysis_queue",
            "analysis_available_at",
            postgresql_where=text("analysis_status = 'pending'"),
            sqlite_where=text("analysis_status = 'pending'"),
        ),
        Index(
            "ix_snapshots_retention",
            "delete_after",
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )


class Directive(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """An instruction from staff to a live session (warn, pause, resume, terminate), delivered with the next heartbeat."""

    __tablename__ = "directives"

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proctor_sessions.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(10))
    message: Mapped[str | None] = mapped_column(String(500))
    issued_by: Mapped[int] = mapped_column(BigInteger)
    delivered_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_directives_session", "session_id", "created_at"),)


class MediaAccess(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Who looked at whose media, and when (docs/PRODUCT.md §5.3: "access-controlled and audited")."""

    __tablename__ = "media_access_log"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("snapshots.id", ondelete="CASCADE"))
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("proctor_sessions.id", ondelete="CASCADE"))
    viewer_user_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(60))  # e.g. "case_review"

    __table_args__ = (Index("ix_media_access_session", "session_id", "created_at"),)

