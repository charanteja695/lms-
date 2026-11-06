from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import WorkStatus


class WorkItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Durable background work, written in the same transaction as the change that needs it and claimed by workers with a lease
    (``FOR UPDATE SKIP LOCKED``): matching a new job, matching an updated profile, screening a new application, inviting a candidate
    to the hiring assessment. A failed item is retried with backoff; after ``WORK_MAX_ATTEMPTS`` it is ``failed`` and visible to staff."""

    __tablename__ = "work_items"

    kind: Mapped[str] = mapped_column(String(20))
    ref_id: Mapped[int] = mapped_column(BigInteger)  # the job / user / application public id it is about
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    status: Mapped[str] = mapped_column(String(8), default=WorkStatus.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    run_after: Mapped[datetime | None]
    leased_until: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(String(300))
    done_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_work_items_status_run", "status", "run_after"), Index("ix_work_items_kind_ref", "kind", "ref_id", "status"))
