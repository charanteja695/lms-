import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import (
    ProctoringLevel,
    ResultVisibility,
    ReviewPolicy,
    ScoreCounting,
    SlotType,
    TestStatus,
    TimeMode,
)


class SectionSlot(UUIDPrimaryKeyMixin, Base):
    """One place in a section's paper: a fixed question, or a pool from which ``count`` questions are drawn per
    student. Marks belong to the slot so a test's total is known when it is published."""

    __tablename__ = "section_slots"

    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_sections.id", ondelete="CASCADE"))
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    slot_type: Mapped[str] = mapped_column(String(6), default=SlotType.FIXED, server_default=SlotType.FIXED)
    question_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("questions.id"))
    criteria: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    marks: Mapped[float] = mapped_column(Float)  # per question

    __table_args__ = (
        UniqueConstraint("section_id", "position", name="uq_section_slots_section_position"),
        Index("ix_section_slots_test", "test_id"),
    )


class TestSection(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "test_sections"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str | None] = mapped_column(Text)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer)  # per-section timing only

    slots: Mapped[list[SectionSlot]] = relationship(
        order_by=SectionSlot.position, cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )

    __table_args__ = (UniqueConstraint("test_id", "position", name="uq_test_sections_test_position"),)


class Test(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A test definition. Editable while a draft; publishing freezes it so a student never sees the rules change
    under them. To change a published test, clone it into a new draft and retire the old one."""

    __tablename__ = "tests"
    __test__ = False  # not a pytest test class

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)  # None: platform test; else one employer's
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    instructions: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(10), default=TestStatus.DRAFT, server_default=TestStatus.DRAFT)
    target_type: Mapped[str | None] = mapped_column(String(10))  # topic / module / course (a final test)
    target_id: Mapped[int | None] = mapped_column(BigInteger)  # the catalog-service id of that target

    time_mode: Mapped[str] = mapped_column(String(12), default=TimeMode.OVERALL, server_default=TimeMode.OVERALL)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)  # overall timing only
    pass_mark_percent: Mapped[int] = mapped_column(Integer, default=60, server_default="60")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")  # 0: unlimited
    cooldown_hours: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    score_counting: Mapped[str] = mapped_column(String(8), default=ScoreCounting.HIGHEST, server_default=ScoreCounting.HIGHEST)
    negative_marking_percent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    shuffle_options: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    result_visibility: Mapped[str] = mapped_column(
        String(15), default=ResultVisibility.IMMEDIATE, server_default=ResultVisibility.IMMEDIATE
    )
    review_policy: Mapped[str] = mapped_column(String(10), default=ReviewPolicy.NONE, server_default=ReviewPolicy.NONE)
    proctoring_level: Mapped[str] = mapped_column(String(10), default=ProctoringLevel.NONE, server_default=ProctoringLevel.NONE)
    requires_schedule: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # Fixed when published, from the sections.
    total_marks: Mapped[float | None] = mapped_column(Float)
    question_count: Mapped[int | None] = mapped_column(Integer)

    created_by: Mapped[int] = mapped_column(BigInteger)
    submitted_at: Mapped[datetime | None]
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None]
    review_note: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None]
    retired_at: Mapped[datetime | None]

    sections: Mapped[list[TestSection]] = relationship(
        order_by=TestSection.position, cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )

    __table_args__ = (
        Index("ix_tests_status_kind", "status", "kind"),
        Index("ix_tests_target", "target_type", "target_id"),
        Index("ix_tests_org", "organization_id"),
    )


class TestSchedule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An exam window (docs/PRODUCT.md §5.1 "staggered starts with a waiting room"). Students prepare their paper
    in the waiting room before ``starts_at``; a start is admitted only inside the window."""

    __tablename__ = "test_schedules"
    __test__ = False

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(String(200))
    organization_id: Mapped[int | None] = mapped_column(BigInteger)  # None: every institution
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    enforce_end: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")  # a late starter is cut off at ends_at
    results_release_at: Mapped[datetime | None]
    created_by: Mapped[int] = mapped_column(BigInteger)
    cancelled_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_test_schedules_test_start", "test_id", "starts_at"),)


class TestAssignment(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """An invitation to take a hiring assessment (job-portal-service invites a shortlisted candidate)."""

    __tablename__ = "test_assignments"
    __test__ = False

    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tests.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger)
    reference: Mapped[str | None] = mapped_column(String(100))  # the caller's application id, echoed in events
    invited_by: Mapped[int | None] = mapped_column(BigInteger)
    opens_at: Mapped[datetime | None]
    expires_at: Mapped[datetime | None]
    max_attempts: Mapped[int | None] = mapped_column(Integer)  # overrides the test's

    __table_args__ = (UniqueConstraint("test_id", "user_id", name="uq_test_assignments_test_user"),)
