import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_public_id
from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType


class JobType(StrEnum):
    USER_EXPORT = "user_export"
    ADMIN_EXPORT = "admin_export"
    INSTITUTION_EXPORT = "institution_export"
    USER_IMPORT = "user_import"
    EMPLOYER_EXPORT = "employer_export"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class BackgroundJob(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Long-running work (large exports and imports) processed by ``python -m app.worker``. ``public_id`` is the API ``job_id``."""

    __tablename__ = "background_jobs"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, default=new_public_id)
    job_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.QUEUED)
    requested_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONType)
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    row_count: Mapped[int | None]
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    error_message: Mapped[str | None] = mapped_column(String(500))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONType)  # import summary
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    expires_at: Mapped[datetime | None]

    __table_args__ = (
        Index("ix_background_jobs_status_created_at", "status", "created_at"),
        Index("ix_background_jobs_requested_by_id_created_at", "requested_by_id", "created_at"),
    )
