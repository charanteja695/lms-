from typing import Any

from sqlalchemy import BigInteger, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType


class CalibrationSample(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A transcript that people have rated, kept to check the AI's rubric scores against (docs/PRODUCT.md §5.8: "calibration against human-rated samples")."""

    __tablename__ = "calibration_samples"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    plan_family_id: Mapped[int] = mapped_column(BigInteger)
    turns: Mapped[list[dict[str, Any]]] = mapped_column(JSONType)  # [{seq, round, speaker, text, elapsed_ms}]
    human_scores: Mapped[dict[str, float]] = mapped_column(JSONType)  # criterion -> 1..5
    human_recommendation: Mapped[str] = mapped_column(String(10))
    rated_by: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (Index("ix_calibration_samples_family", "plan_family_id"),)


class CalibrationRun(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "calibration_runs"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    plan_family_id: Mapped[int] = mapped_column(BigInteger)
    prompt_version: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str | None] = mapped_column(String(80))
    samples: Mapped[int] = mapped_column(Integer)
    mean_abs_error: Mapped[float | None] = mapped_column(Float)  # average distance between the AI's and the humans' criterion scores
    within_one_rate: Mapped[float | None] = mapped_column(Float)  # share of criterion scores within one point of the humans'
    recommendation_agreement: Mapped[float | None] = mapped_column(Float)
    details: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    run_by: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (Index("ix_calibration_runs_family", "plan_family_id", "created_at"),)
