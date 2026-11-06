from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType


class CandidatePreference(TimestampMixin, Base):
    """What a student says they want: part of the match (20 of 100 points). Optional — a preference left unset earns half its points,
    so a student who set nothing is neither favoured nor penalised."""

    __tablename__ = "candidate_preferences"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    locations: Mapped[list[str]] = mapped_column(JSONType, default=list)
    open_to_remote: Mapped[bool] = mapped_column(Boolean, default=True)
    roles: Mapped[list[str]] = mapped_column(JSONType, default=list)
    min_ctc: Mapped[int | None] = mapped_column(BigInteger)
    employment_types: Mapped[list[str]] = mapped_column(JSONType, default=list)
    open_to_work: Mapped[bool] = mapped_column(Boolean, default=True)  # false: no recommendations and no match notifications


class JobMatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A candidate's match with a job: eligible, and scored. Only matches at or above ``MATCH_STORE_MIN_SCORE`` are kept. Recomputed when the
    job or the profile changes (``job_revision`` / ``profile_revision`` say which versions the score used)."""

    __tablename__ = "job_matches"

    job_id: Mapped[Any] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger)
    score: Mapped[int] = mapped_column(Integer)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSONType)  # points per component
    explanation: Mapped[list[str]] = mapped_column(JSONType)
    semantic_method: Mapped[str] = mapped_column(String(8))  # dense | lexical
    semantic_similarity: Mapped[float] = mapped_column(Float, default=0.0)
    job_revision: Mapped[int] = mapped_column(Integer)
    profile_revision: Mapped[int] = mapped_column(Integer)
    notified_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("job_id", "user_id", name="uq_job_matches_job_user"),
        Index("ix_job_matches_user_score", "user_id", "score"),
        Index("ix_job_matches_job_score", "job_id", "score"),
    )
