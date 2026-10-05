from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, NullableJSONType
from app.domain.enums import AppealStatus, EvaluationStatus, InterviewStatus


class Interview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "interviews"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    plan_id: Mapped[int] = mapped_column(BigInteger)  # the plan's public id
    plan_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType)  # the plan as it was when the interview was created
    user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)  # the candidate's institution: billing mock interviews and the fairness audit only
    kind: Mapped[str] = mapped_column(String(10))
    # a screening interview belongs to an application in job-portal-service
    application_id: Mapped[int | None] = mapped_column(BigInteger)
    job_id: Mapped[int | None] = mapped_column(BigInteger)
    employer_org_id: Mapped[int | None] = mapped_column(BigInteger)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(12), default=InterviewStatus.INVITED)
    invite_expires_at: Mapped[datetime | None]
    consent: Mapped[dict[str, Any] | None] = mapped_column(NullableJSONType)  # {version, accepted_at, recording}
    proctoring_level: Mapped[str] = mapped_column(String(8), default="none")
    integrity_status: Mapped[str | None] = mapped_column(String(20))
    started_at: Mapped[datetime | None]
    ends_at: Mapped[datetime | None]  # the server's clock: the interview ends here whatever the client says
    completed_at: Mapped[datetime | None]
    complete_reason: Mapped[str | None] = mapped_column(String(20))  # finished | time_up | candidate_ended | abandoned
    round_index: Mapped[int] = mapped_column(Integer, default=0)
    round_started_at: Mapped[datetime | None]
    question_index: Mapped[int] = mapped_column(Integer, default=0)  # which core question of the round is being asked
    follow_ups: Mapped[int] = mapped_column(Integer, default=0)  # follow-ups asked on the current question
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    awaiting_reply_since: Mapped[datetime | None]  # set while the interviewer's reply to the last answer is being produced: one answer at a time
    code_runs: Mapped[int] = mapped_column(Integer, default=0)
    # the person's review of the AI's recommendation
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None]
    final_recommendation: Mapped[str | None] = mapped_column(String(10))
    review_note: Mapped[str | None] = mapped_column(String(500))
    feedback_released: Mapped[bool] = mapped_column(Boolean, default=False)
    retake_granted: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_interviews_user", "user_id", "created_at"),
        Index("ix_interviews_app", "application_id"),
        Index("ix_interviews_plan_status", "plan_id", "status"),
        Index("ix_interviews_employer", "employer_org_id", "status"),
        Index("ix_interviews_status_ends", "status", "ends_at"),
    )


class InterviewTurn(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One thing said or done in an interview. The transcript is these, in ``seq`` order; ``elapsed_ms`` counts from the start of the interview, so an
    evaluation's evidence can point at a moment."""

    __tablename__ = "interview_turns"

    interview_id: Mapped[Any] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    round_key: Mapped[str] = mapped_column(String(30))
    speaker: Mapped[str] = mapped_column(String(12))
    kind: Mapped[str] = mapped_column(String(12))
    text: Mapped[str] = mapped_column(Text)
    elapsed_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    via: Mapped[str] = mapped_column(String(6), default="text")  # text | audio
    meta: Mapped[dict[str, Any] | None] = mapped_column(NullableJSONType)  # code turns: language, run id, outcome

    __table_args__ = (
        UniqueConstraint("interview_id", "seq", name="uq_interview_turns_seq"),
        UniqueConstraint("interview_id", "idempotency_key", name="uq_interview_turns_key"),
    )


class Evaluation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """The rubric result for an interview. The model scores and quotes; this service verifies every quote against the transcript, clamps a score
    that has no evidence, and computes the recommendation from the weighted score — the model never chooses it."""

    __tablename__ = "evaluations"

    interview_id: Mapped[Any] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(8), default=EvaluationStatus.PENDING)
    model: Mapped[str | None] = mapped_column(String(80))
    prompt_key: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[int | None] = mapped_column(Integer)
    ai_call_id: Mapped[int | None] = mapped_column(BigInteger)
    input_digest: Mapped[str | None] = mapped_column(String(64))
    rounds: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)  # [{round, scores: {criterion: {score, evidence[]}}, comment}]
    criterion_scores: Mapped[dict[str, float]] = mapped_column(JSONType, default=dict)
    overall_score: Mapped[float | None] = mapped_column(Float)
    recommendation: Mapped[str | None] = mapped_column(String(10))
    summary: Mapped[str | None] = mapped_column(Text)
    strengths: Mapped[list[str]] = mapped_column(JSONType, default=list)
    improvements: Mapped[list[str]] = mapped_column(JSONType, default=list)
    flags: Mapped[list[str]] = mapped_column(JSONType, default=list)
    improvement_plan: Mapped[str | None] = mapped_column(Text)  # a candidate-facing plan for a mock interview
    invalid_quotes: Mapped[int] = mapped_column(Integer, default=0)
    total_quotes: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(300))


class Appeal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A candidate's appeal of a screening result; if upheld they are granted a retake (docs/PRODUCT.md §5.8: "appeal/retake follows the policy")."""

    __tablename__ = "appeals"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    interview_id: Mapped[Any] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(8), default=AppealStatus.OPEN)
    decided_by: Mapped[int | None] = mapped_column(BigInteger)
    decided_at: Mapped[datetime | None]
    decision_note: Mapped[str | None] = mapped_column(String(500))
