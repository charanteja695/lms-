import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utcnow
from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import AttemptResult, AttemptStatus, CodingStatus, IntegrityStatus


class AttemptQuestion(UUIDPrimaryKeyMixin, Base):
    """One question of one student's paper, pinned to the exact version served. The paper is generated once, when
    the attempt is prepared, and never changes."""

    __tablename__ = "attempt_questions"

    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)  # 1-based order in the paper
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_sections.id"))
    section_position: Mapped[int] = mapped_column(Integer)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id"))
    question_public_id: Mapped[int] = mapped_column(BigInteger)
    question_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_versions.id"))
    marks: Mapped[float] = mapped_column(Float)
    option_order: Mapped[list[str] | None] = mapped_column(JSONType)  # this student's shuffled option/item order

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_public_id", name="uq_attempt_questions_attempt_question"),
        Index("ix_attempt_questions_attempt_position", "attempt_id", "position"),
        Index("ix_attempt_questions_question", "question_id"),
    )


class AttemptSection(UUIDPrimaryKeyMixin, Base):
    """Per-section timing: each section has its own clock, and a finished section cannot be reopened."""

    __tablename__ = "attempt_sections"

    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_sections.id"))
    position: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime | None]
    deadline_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    __table_args__ = (UniqueConstraint("attempt_id", "position", name="uq_attempt_sections_attempt_position"),)


class AttemptAnswer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A student's answer and its grade. Rows are created when the buffered answer is flushed (or at grading for
    a question left unanswered), so a started paper costs no answer rows until the student writes something."""

    __tablename__ = "attempt_answers"

    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    question_public_id: Mapped[int] = mapped_column(BigInteger)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")  # the client's, so a stale save loses
    flagged: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # marked for review by the student

    grading_status: Mapped[str | None] = mapped_column(String(15))
    marks_awarded: Mapped[float | None] = mapped_column(Float)
    max_marks: Mapped[float | None] = mapped_column(Float)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    feedback: Mapped[str | None] = mapped_column(Text)
    rubric_scores: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    graded_by: Mapped[int | None] = mapped_column(BigInteger)  # None: graded automatically
    graded_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_public_id", name="uq_attempt_answers_attempt_question"),
        Index(
            "ix_attempt_answers_pending_manual",
            "attempt_id",
            postgresql_where=text("grading_status = 'pending_manual'"),
            sqlite_where=text("grading_status = 'pending_manual'"),
        ),
    )


class AttemptEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """The attempt's audit trail: start, every resume, pauses, submission, grading, overrides."""

    __tablename__ = "attempt_events"

    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(30))
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    __table_args__ = (Index("ix_attempt_events_attempt_created", "attempt_id", "created_at"),)


class CodingSubmission(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A coding or SQL answer on its way to code-execution-service and back. A row is the durable record that the
    answer must be judged: the dispatcher retries until code-execution accepts it, and the verdict is matched back
    by ``reference`` (from the ``submission.judged`` event, or by asking directly if the event never comes)."""

    __tablename__ = "coding_submissions"

    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attempts.id", ondelete="CASCADE"))
    attempt_public_id: Mapped[int] = mapped_column(BigInteger)
    question_public_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    problem_id: Mapped[int] = mapped_column(BigInteger)  # code-execution-service's problem
    language: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(Text)
    reference: Mapped[str] = mapped_column(String(100), unique=True)  # "attempt:<attempt id>:<question id>"
    status: Mapped[str] = mapped_column(String(12), default=CodingStatus.PENDING, server_default=CodingStatus.PENDING)
    dispatch_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(default=utcnow)
    dispatched_at: Mapped[datetime | None]
    code_submission_id: Mapped[int | None] = mapped_column(BigInteger)
    last_error: Mapped[str | None] = mapped_column(String(300))

    verdict: Mapped[str | None] = mapped_column(String(30))
    passed_count: Mapped[int | None] = mapped_column(Integer)
    total_count: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[int | None] = mapped_column(Integer)  # 0-100, weighted by code-execution's test case weights
    judged_at: Mapped[datetime | None]
    flagged: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # plagiarism signal
    similarity_percent: Mapped[int | None] = mapped_column(Integer)
    similar_to_submission_id: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        UniqueConstraint("attempt_id", "question_public_id", name="uq_coding_submissions_attempt_question"),
        Index(
            "ix_coding_submissions_open",
            "status",
            "available_at",
            postgresql_where=text("status IN ('pending', 'dispatched')"),
            sqlite_where=text("status IN ('pending', 'dispatched')"),
        ),
        Index(
            "ix_coding_submissions_flagged",
            "attempt_id",
            postgresql_where=text("flagged"),
            sqlite_where=text("flagged"),
        ),
    )


class Attempt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One student's try at a test (docs/PRODUCT.md §5.1 lifecycle). It is also the grading queue row: a submitted
    attempt is claimed by a grader with a lease, exactly as code-execution-service claims its jobs."""

    __tablename__ = "attempts"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id"))
    test_public_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    attempt_no: Mapped[int] = mapped_column(Integer)  # counts started attempts only; 0 while only prepared
    status: Mapped[str] = mapped_column(String(12), default=AttemptStatus.NOT_STARTED, server_default=AttemptStatus.NOT_STARTED)
    seed: Mapped[int] = mapped_column(BigInteger)  # the paper is a pure function of this and the test
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_schedules.id"))
    # The learning context, from the enrolment read-model (None for practice and hiring tests).
    enrollment_id: Mapped[int | None] = mapped_column(BigInteger)
    version_id: Mapped[int | None] = mapped_column(BigInteger)
    course_id: Mapped[int | None] = mapped_column(BigInteger)

    started_at: Mapped[datetime | None]
    deadline_at: Mapped[datetime | None]  # the server-side authority for when the attempt ends
    paused_at: Mapped[datetime | None]
    submitted_at: Mapped[datetime | None]
    submit_reason: Mapped[str | None] = mapped_column(String(12))
    resume_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    client_ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))

    # Grading queue (only meaningful while status is submitted/grading).
    grading_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    grading_available_at: Mapped[datetime | None]
    graded_at: Mapped[datetime | None]

    score: Mapped[float | None] = mapped_column(Float)  # never below 0
    max_score: Mapped[float | None] = mapped_column(Float)
    percent: Mapped[float | None] = mapped_column(Float)
    plagiarism_flagged: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    integrity_status: Mapped[str] = mapped_column(
        String(15), default=IntegrityStatus.NOT_REQUIRED, server_default=IntegrityStatus.NOT_REQUIRED
    )
    integrity_decided_at: Mapped[datetime | None]
    result: Mapped[str] = mapped_column(String(12), default=AttemptResult.PENDING, server_default=AttemptResult.PENDING)
    finalized_at: Mapped[datetime | None]
    finalize_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # A decided result becomes official when it is released: immediately, at the end of the exam window, or when
    # staff release it (test.result_visibility). Only then is it shown to the student and announced to other services.
    release_due_at: Mapped[datetime | None]
    results_visible_at: Mapped[datetime | None]  # set when released

    questions: Mapped[list[AttemptQuestion]] = relationship(
        order_by=AttemptQuestion.position, cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )
    sections: Mapped[list[AttemptSection]] = relationship(
        order_by=AttemptSection.position, cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )

    __table_args__ = (
        Index("ix_attempts_user_test", "user_id", "test_id", "created_at"),
        Index("ix_attempts_test_status", "test_id", "status"),
        Index("ix_attempts_test_result", "test_id", "result"),
        Index("ix_attempts_org_created", "organization_id", "created_at"),
        Index(
            "ix_attempts_deadline",
            "deadline_at",
            postgresql_where=text("status = 'in_progress'"),
            sqlite_where=text("status = 'in_progress'"),
        ),
        Index(
            "ix_attempts_grading_queue",
            "grading_available_at",
            postgresql_where=text("status = 'submitted'"),
            sqlite_where=text("status = 'submitted'"),
        ),
        # A student has at most one live attempt per test: a double click or a second tab gets the same paper.
        Index(
            "uq_attempts_one_open",
            "user_id",
            "test_id",
            unique=True,
            postgresql_where=text("status IN ('not_started', 'in_progress', 'paused')"),
            sqlite_where=text("status IN ('not_started', 'in_progress', 'paused')"),
        ),
        Index(
            "ix_attempts_release_due",
            "release_due_at",
            postgresql_where=text("results_visible_at IS NULL AND release_due_at IS NOT NULL"),
            sqlite_where=text("results_visible_at IS NULL AND release_due_at IS NOT NULL"),
        ),
        Index(
            "ix_attempts_integrity_pending",
            "graded_at",
            postgresql_where=text("integrity_status IN ('pending', 'flagged', 'under_review')"),
            sqlite_where=text("integrity_status IN ('pending', 'flagged', 'under_review')"),
        ),
    )
