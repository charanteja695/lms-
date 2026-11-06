import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import QuestionStatus, VersionStatus


class Question(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A question's stable identity. Its content lives in immutable ``QuestionVersion`` rows: editing a published
    question opens a new draft version, and only an approved version replaces the current one, so a test being
    taken is never changed under a student (attempts pin the version they were served)."""

    __tablename__ = "questions"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    question_type: Mapped[str] = mapped_column(String(20))
    organization_id: Mapped[int | None] = mapped_column(BigInteger)  # None: platform bank; else one employer's
    status: Mapped[str] = mapped_column(String(10), default=QuestionStatus.ACTIVE, server_default=QuestionStatus.ACTIVE)
    current_version_no: Mapped[int | None] = mapped_column(Integer)  # the published version, if any
    latest_version_no: Mapped[int] = mapped_column(Integer, default=1, server_default="1")  # published or not
    created_by: Mapped[int] = mapped_column(BigInteger)

    versions: Mapped[list["QuestionVersion"]] = relationship(
        order_by="QuestionVersion.version_no", cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )

    __table_args__ = (Index("ix_questions_org_status", "organization_id", "status"),)


class QuestionVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "question_versions"

    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    version_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default=VersionStatus.DRAFT, server_default=VersionStatus.DRAFT)
    text: Mapped[str] = mapped_column(Text)  # the stem, markdown
    body: Mapped[dict[str, Any]] = mapped_column(JSONType)  # what the student sees: options, items, problem ref...
    answer_key: Mapped[dict[str, Any]] = mapped_column(JSONType)  # never sent to a student before results
    explanation: Mapped[str | None] = mapped_column(Text)
    default_marks: Mapped[float] = mapped_column(Float, default=1.0, server_default="1")
    difficulty: Mapped[int] = mapped_column(Integer, default=3, server_default="3")  # 1 (easiest) .. 5
    bloom: Mapped[str | None] = mapped_column(String(12))
    created_by: Mapped[int] = mapped_column(BigInteger)
    submitted_at: Mapped[datetime | None]
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None]
    review_note: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None]

    tags: Mapped[list["QuestionVersionTag"]] = relationship(cascade="all, delete-orphan", passive_deletes=True, lazy="raise")

    __table_args__ = (
        UniqueConstraint("question_id", "version_no", name="uq_question_versions_question_version"),
        Index("ix_question_versions_status", "status"),
        Index("ix_question_versions_difficulty", "difficulty"),
    )


class QuestionVersionTag(Base):
    """A skill, topic or free tag on a version. A table (not a JSON list) so a pool can filter on it in SQL on
    every database this service runs on."""

    __tablename__ = "question_version_tags"

    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("question_versions.id", ondelete="CASCADE"), primary_key=True)
    tag_type: Mapped[str] = mapped_column(String(10), primary_key=True)
    value: Mapped[str] = mapped_column(String(60), primary_key=True)

    __table_args__ = (Index("ix_question_version_tags_lookup", "tag_type", "value", "version_id"),)


class QuestionStats(CreatedAtMixin, Base):
    """Usage statistics computed after attempts (docs/PRODUCT.md §5.1): difficulty index (the average share of the
    marks students earned: high means easy) and discrimination (top 27% minus bottom 27% of scorers on this
    question: high means it separates strong from weak)."""

    __tablename__ = "question_stats"

    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    sample_size: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    difficulty_index: Mapped[float | None] = mapped_column(Float)
    discrimination: Mapped[float | None] = mapped_column(Float)
    computed_at: Mapped[datetime]
