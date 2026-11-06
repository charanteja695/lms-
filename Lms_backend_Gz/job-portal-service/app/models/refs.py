"""Read-models built from other services' events. Nothing here is edited through this service's API."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, NullableJSONType


class OrgRef(TimestampMixin, Base):
    """From ``institution.*`` and ``employer.*``: who an organisation is, and whether it is active."""

    __tablename__ = "org_refs"

    org_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200), default="")
    org_type: Mapped[str] = mapped_column(String(12), default="")  # institution | employer
    industry: Mapped[str | None] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserRef(TimestampMixin, Base):
    """From ``user.*``: who a recruiter, institution member or candidate is (names are shown to people who may see them; never scored)."""

    __tablename__ = "user_refs"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    email: Mapped[str | None] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(20), default="")
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CourseRef(TimestampMixin, Base):
    __tablename__ = "course_refs"

    course_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(300), default="")


class CandidateProfile(TimestampMixin, Base):
    """From career-service's ``skill_profile.updated``: the facts a hiring decision may look at (skills, technologies, role titles,
    months of experience, education, graduation year, verified certificates and scores). No name, email, photo, date of birth,
    gender or institution is in it, so scoring cannot use them. ``embedding`` is the profile's vector (NULL until embedded)."""

    __tablename__ = "candidate_profiles"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)  # the candidate's institution: eligibility and drives, never scoring
    revision: Mapped[int] = mapped_column(Integer, default=0)
    facts: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(NullableJSONType)
    embedding_revision: Mapped[int | None] = mapped_column(Integer)
    updated_by_event_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_candidate_profiles_org", "organization_id"),)


class HiringResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A released hiring-test result (``attempt.finalized`` with ``test_kind: hiring``). The pipeline reads it to complete the
    assessment stage; assessment-service has already folded the integrity decision into the result and its ``revision``."""

    __tablename__ = "hiring_results"

    attempt_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    test_id: Mapped[int] = mapped_column(BigInteger)
    percent: Mapped[float | None] = mapped_column(Float)
    result: Mapped[str] = mapped_column(String(12))
    integrity_status: Mapped[str | None] = mapped_column(String(20))
    revision: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("attempt_id", name="uq_hiring_results_attempt"), Index("ix_hiring_results_user_test", "user_id", "test_id"))
