from datetime import datetime

from sqlalchemy import BigInteger, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import CompareMode, Difficulty, ProblemStatus, ProblemType
from app.models.test_case import TestCase


class Problem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A coding or SQL problem. Editable while a draft; publishing freezes it (students may then
    submit), so verdicts already given never change under a student. To change a published problem,
    retire it and author a new one."""

    __tablename__ = "problems"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    title: Mapped[str] = mapped_column(String(200))
    statement: Mapped[str] = mapped_column(Text)  # markdown
    problem_type: Mapped[str] = mapped_column(String(10), default=ProblemType.CODE, server_default=ProblemType.CODE)
    difficulty: Mapped[str] = mapped_column(String(10), default=Difficulty.EASY, server_default=Difficulty.EASY)
    tags: Mapped[list[str]] = mapped_column(JSONType)
    status: Mapped[str] = mapped_column(String(15), default=ProblemStatus.DRAFT, server_default=ProblemStatus.DRAFT)
    time_limit_ms: Mapped[int] = mapped_column(Integer, default=2_000, server_default="2000")
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256, server_default="256")
    # Language codes a student may use; empty means every enabled language of the problem's type.
    allowed_languages: Mapped[list[str]] = mapped_column(JSONType)
    # SQL problems: schema and seed data run before the student's query. Encrypted; never sent to clients.
    setup_sql_encrypted: Mapped[str | None] = mapped_column(Text)
    compare_mode: Mapped[str] = mapped_column(String(20), default=CompareMode.TRIM, server_default=CompareMode.TRIM)
    float_tolerance: Mapped[float] = mapped_column(Float, default=1e-6, server_default="0.000001")
    created_by: Mapped[int] = mapped_column(BigInteger)
    published_at: Mapped[datetime | None]
    retired_at: Mapped[datetime | None]

    test_cases: Mapped[list[TestCase]] = relationship(
        order_by=TestCase.position, cascade="all, delete-orphan", passive_deletes=True, lazy="raise"
    )

    __table_args__ = (
        Index("ix_problems_status_created", "status", "created_at"),
        Index("ix_problems_difficulty", "difficulty"),
    )
