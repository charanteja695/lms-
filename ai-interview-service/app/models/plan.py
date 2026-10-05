from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import PlanStatus


class InterviewPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """What an interview is: the role, the rounds, their questions and time, and the rubric. The *same* plan and rubric are used for
    every candidate of a job (docs/PRODUCT.md §5.8 "Fairness"). A published plan never changes; to change it, publish a new version
    (a new row with the same ``family_id``). An interview freezes the plan it was given."""

    __tablename__ = "interview_plans"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    family_id: Mapped[int] = mapped_column(BigInteger)  # every version of one plan shares it
    version: Mapped[int] = mapped_column(Integer, default=1)
    owner_org_id: Mapped[int | None] = mapped_column(BigInteger)  # the employer that owns a screening plan; null for the platform's mock plans
    kind: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(120))
    skills: Mapped[list[str]] = mapped_column(JSONType, default=list)
    difficulty: Mapped[str] = mapped_column(String(8))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    rounds: Mapped[list[dict[str, Any]]] = mapped_column(JSONType)  # [{key, type, minutes, questions[], languages[], criteria[]}]
    criteria_weights: Mapped[dict[str, float]] = mapped_column(JSONType)  # rubric weights, summing to 1
    instructions: Mapped[str | None] = mapped_column(Text)  # what the candidate is told before consenting
    proctoring_level: Mapped[str] = mapped_column(String(8), default="none")  # none | basic | strict (screening interviews)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    retake_cooldown_days: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(10), default=PlanStatus.DRAFT)
    created_by: Mapped[int] = mapped_column(BigInteger)
    published_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_interview_plans_owner", "owner_org_id", "kind", "status"), Index("ix_interview_plans_family", "family_id", "version"))
