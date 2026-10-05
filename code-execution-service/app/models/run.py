from datetime import datetime

from sqlalchemy import BigInteger, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.domain.enums import JobStatus


class Run(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A run of some code on custom input. Also a queue row: a worker claims it with a lease
    (``available_at`` pushed forward), executes it, and records the outcome on the row."""

    __tablename__ = "runs"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    language_code: Mapped[str] = mapped_column(String(30))
    problem_public_id: Mapped[int | None] = mapped_column(BigInteger)  # SQL runs use the problem's schema
    source: Mapped[str] = mapped_column(Text)
    stdin: Mapped[str] = mapped_column(Text, default="", server_default="")
    priority: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(15), default=JobStatus.QUEUED, server_default=JobStatus.QUEUED)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(default=utcnow)

    outcome: Mapped[str | None] = mapped_column(String(30))  # ok, runtime_error, time_limit_exceeded, ...
    stdout: Mapped[str | None] = mapped_column(Text)
    stderr: Mapped[str | None] = mapped_column(Text)
    compile_output: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(String(500))
    time_ms: Mapped[int | None] = mapped_column(Integer)
    memory_kb: Mapped[int | None] = mapped_column(Integer)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    __table_args__ = (
        Index(
            "ix_runs_queue",
            "priority",
            "available_at",
            postgresql_where=text("status <> 'completed'"),
            sqlite_where=text("status <> 'completed'"),
        ),
        Index("ix_runs_user_created", "user_id", "created_at"),
        Index("ix_runs_created", "created_at"),
    )
