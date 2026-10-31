from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, NullableJSONType
from app.domain.enums import JobStatus, Visibility


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A job posting. ``draft → pending_approval → open → paused → closed``; a platform admin approves before it opens."""

    __tablename__ = "jobs"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    employer_org_id: Mapped[int] = mapped_column(BigInteger)
    created_by: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    employment_type: Mapped[str] = mapped_column(String(12))
    location_type: Mapped[str] = mapped_column(String(8))
    locations: Mapped[list[str]] = mapped_column(JSONType, default=list)
    experience_min_months: Mapped[int] = mapped_column(Integer, default=0)
    experience_max_months: Mapped[int | None] = mapped_column(Integer)
    ctc_min: Mapped[int | None] = mapped_column(BigInteger)  # whole units per year, in ``currency``
    ctc_max: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    # internships: monthly stipend (whole units of ``currency``) and how long it runs
    stipend_per_month: Mapped[int | None] = mapped_column(BigInteger)
    duration_months: Mapped[int | None] = mapped_column(Integer)
    required_skills: Mapped[list[str]] = mapped_column(JSONType, default=list)
    preferred_skills: Mapped[list[str]] = mapped_column(JSONType, default=list)
    openings: Mapped[int] = mapped_column(Integer, default=1)
    deadline_at: Mapped[datetime | None]
    # eligibility (hard rules, applied before any scoring): {"graduation_years": {"min","max"}|null, "certificate_course_ids": [...],
    # "min_scores": [{"course_id","min_percent"}], }; the institutions live in ``job_institutions`` so they can be queried
    eligibility: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    visibility: Mapped[str] = mapped_column(String(10), default=Visibility.PUBLIC)
    drive_id: Mapped[int | None] = mapped_column(BigInteger)  # the placement drive this job belongs to
    # hiring pipeline template: {"assessment": {"test_id","min_percent"}|null, "ai_interview": {"plan_id"}|null, "hr_interview": bool}
    pipeline: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.DRAFT)
    revision: Mapped[int] = mapped_column(Integer, default=0)  # bumped when anything a match depends on changes
    submitted_at: Mapped[datetime | None]
    approved_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None]
    review_note: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    closed_reason: Mapped[str | None] = mapped_column(String(200))
    embedding: Mapped[list[float] | None] = mapped_column(NullableJSONType)
    embedding_revision: Mapped[int | None] = mapped_column(Integer)
    job_code: Mapped[str | None] = mapped_column(String(32))
    job_details: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    hiring_process: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    application_config: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    banner_text: Mapped[str | None] = mapped_column(Text)
    banner_type: Mapped[str | None] = mapped_column(String(20), default="info")
    experience_level: Mapped[str | None] = mapped_column(String(20))
    experience_level_description: Mapped[str | None] = mapped_column(Text)
    remote_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    about_job: Mapped[str | None] = mapped_column(Text)
    responsibilities: Mapped[list[str]] = mapped_column(JSONType, default=list)
    minimum_qualifications: Mapped[list[str]] = mapped_column(JSONType, default=list)
    preferred_qualifications: Mapped[list[str]] = mapped_column(JSONType, default=list)
    perks: Mapped[list[str]] = mapped_column(JSONType, default=list)

    __table_args__ = (
        Index("ix_jobs_employer_status", "employer_org_id", "status"),
        Index("ix_jobs_status_published", "status", "published_at"),
        Index("ix_jobs_drive", "drive_id"),
    )


class JobInstitution(UUIDPrimaryKeyMixin, Base):
    """The institutions a restricted job is open to (empty for a public job)."""

    __tablename__ = "job_institutions"

    job_id: Mapped[Any] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    organization_id: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (UniqueConstraint("job_id", "organization_id", name="uq_job_institutions_job_org"), Index("ix_job_institutions_org", "organization_id"))
