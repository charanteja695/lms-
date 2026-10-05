from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import ApplicationStatus


class Application(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One student's application to one job (unique). ``resume_snapshot`` is the resume as it was when they applied — frozen by
    career-service — so later edits never change what the recruiter is judging."""

    __tablename__ = "applications"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    job_id: Mapped[Any] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    employer_org_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)  # the candidate's institution
    status: Mapped[str] = mapped_column(String(24), default=ApplicationStatus.APPLIED)
    status_changed_at: Mapped[datetime | None]
    cover_note: Mapped[str | None] = mapped_column(Text)
    resume_id: Mapped[int] = mapped_column(BigInteger)
    resume_version_no: Mapped[int] = mapped_column(Integer)
    resume_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType)
    match_score: Mapped[int | None] = mapped_column(Integer)  # the match score when they applied
    match_explanation: Mapped[list[str] | None] = mapped_column(JSONType)
    # screening: the rule-based fit and, when the model was available, its opinion. Both are recommendations.
    screen_score: Mapped[int | None] = mapped_column(Integer)
    screen_reasons: Mapped[list[str] | None] = mapped_column(JSONType)
    screen_red_flags: Mapped[list[str] | None] = mapped_column(JSONType)
    screen_source: Mapped[str | None] = mapped_column(String(12))  # ai | rules
    screen_recommendation: Mapped[str | None] = mapped_column(String(10))  # shortlist | review | reject: a recommendation, never an action
    screened_at: Mapped[datetime | None]
    # the hiring assessment
    assessment_test_id: Mapped[int | None] = mapped_column(BigInteger)
    assessment_invited_at: Mapped[datetime | None]
    assessment_invite_state: Mapped[str | None] = mapped_column(String(10))  # pending | sent | failed
    assessment_percent: Mapped[float | None] = mapped_column(Float)
    assessment_result: Mapped[str | None] = mapped_column(String(12))
    assessment_integrity: Mapped[str | None] = mapped_column(String(20))
    assessment_attempt_id: Mapped[int | None] = mapped_column(BigInteger)
    assessment_revision: Mapped[int] = mapped_column(Integer, default=0)
    # the AI interview (phase 10 fills these)
    interview_recommendation: Mapped[str | None] = mapped_column(String(12))
    interview_score: Mapped[float | None] = mapped_column(Float)
    interview_report: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    hr_interview_at: Mapped[datetime | None]
    hr_interview_note: Mapped[str | None] = mapped_column(String(500))
    decision_reason: Mapped[str | None] = mapped_column(String(500))  # why it was rejected / withdrawn

    __table_args__ = (
        UniqueConstraint("job_id", "user_id", name="uq_applications_job_user"),
        Index("ix_applications_job_status", "job_id", "status"),
        Index("ix_applications_user", "user_id", "created_at"),
        Index("ix_applications_org", "organization_id", "status"),
        Index("ix_applications_employer", "employer_org_id", "status"),
    )


class ApplicationStage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """The history of an application: every status it has been in, who moved it, and why."""

    __tablename__ = "application_stages"

    application_id: Mapped[Any] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    actor: Mapped[str] = mapped_column(String(10))
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(String(500))
    batch_id: Mapped[int | None] = mapped_column(BigInteger)  # the rejection batch that confirmed it

    __table_args__ = (Index("ix_application_stages_app", "application_id", "created_at"),)


class ApplicationNote(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A recruiter's private note. The candidate never sees these."""

    __tablename__ = "application_notes"

    application_id: Mapped[Any] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    author_user_id: Mapped[int] = mapped_column(BigInteger)
    body: Mapped[str] = mapped_column(Text)

    __table_args__ = (Index("ix_application_notes_app", "application_id", "created_at"),)


class RejectionBatch(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A person's confirmation of a set of rejections (docs/PRODUCT.md §5.7: "a human confirms each rejection batch"). It records who,
    when, why, how many the screening had recommended rejecting, and how many the person rejected that it had *not*."""

    __tablename__ = "rejection_batches"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    job_id: Mapped[Any] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    confirmed_by: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(500))
    application_ids: Mapped[list[int]] = mapped_column(JSONType)
    recommended_count: Mapped[int] = mapped_column(Integer, default=0)
    not_recommended_count: Mapped[int] = mapped_column(Integer, default=0)
    threshold: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (Index("ix_rejection_batches_job", "job_id", "created_at"),)


class AiDecision(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Every AI screening decision, logged with the model and prompt version for audit and bias review (docs/PRODUCT.md §5.7). The input
    is stored as it was sent — which by construction holds no name, email, photo, gender, age or institution."""

    __tablename__ = "ai_decisions"

    job_id: Mapped[Any] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    application_id: Mapped[Any] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(8))  # ai | rules
    model: Mapped[str | None] = mapped_column(String(80))
    prompt_key: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[int | None] = mapped_column(Integer)
    ai_call_id: Mapped[int | None] = mapped_column(BigInteger)
    input_digest: Mapped[str] = mapped_column(String(64))
    input: Mapped[dict[str, Any]] = mapped_column(JSONType)
    output: Mapped[dict[str, Any]] = mapped_column(JSONType)
    score: Mapped[int | None] = mapped_column(Integer)
    recommendation: Mapped[str] = mapped_column(String(12))  # shortlist | review | reject (a recommendation, never an action)

    __table_args__ = (Index("ix_ai_decisions_job", "job_id", "created_at"), Index("ix_ai_decisions_app", "application_id", "created_at"))
