import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.domain.enums import JobStatus
from app.models.submission_result import SubmissionResult


class Submission(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A solution submitted to a problem, judged against every test case. Like ``Run`` it is a queue
    row claimed by a worker; the verdict is the first failing case's verdict (or accepted)."""

    __tablename__ = "submissions"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("problems.id"))
    problem_public_id: Mapped[int] = mapped_column(BigInteger)
    language_code: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(Text)
    # Opaque id from the caller (assessment-service's attempt), echoed in submission.judged.
    reference: Mapped[str | None] = mapped_column(String(100))
    priority: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(15), default=JobStatus.QUEUED, server_default=JobStatus.QUEUED)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(default=utcnow)

    verdict: Mapped[str | None] = mapped_column(String(30))
    passed_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # weighted, 0-100
    time_ms: Mapped[int | None] = mapped_column(Integer)  # slowest case
    memory_kb: Mapped[int | None] = mapped_column(Integer)  # largest case
    compile_output: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(String(500))
    judged_at: Mapped[datetime | None]

    fingerprint_count: Mapped[int | None] = mapped_column(Integer)
    similarity_percent: Mapped[int | None] = mapped_column(Integer)  # highest match with another submission
    similar_to_public_id: Mapped[int | None] = mapped_column(BigInteger)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    results: Mapped[list[SubmissionResult]] = relationship(
        order_by=SubmissionResult.position, cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )

    __table_args__ = (
        Index(
            "ix_submissions_queue",
            "priority",
            "available_at",
            postgresql_where=text("status <> 'completed'"),
            sqlite_where=text("status <> 'completed'"),
        ),
        Index("ix_submissions_user_created", "user_id", "created_at"),
        Index("ix_submissions_problem_created", "problem_id", "created_at"),
        Index("ix_submissions_reference", "reference"),
        Index(
            "ix_submissions_flagged",
            "problem_id",
            postgresql_where=text("flagged"),
            sqlite_where=text("flagged"),
        ),
    )
