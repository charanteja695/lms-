"""Read-models built from other services' events. Nothing here is edited by a student."""

from sqlalchemy import BigInteger, Boolean, Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserRef(TimestampMixin, Base):
    """From user-management's ``user.*`` events: the verified personal details printed on a resume."""

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


class AttemptResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A released test result (``attempt.finalized``). A student's *skill score* for a course is their best valid percent
    here; keeping every attempt means an integrity ruling that invalidates one lowers the score correctly."""

    __tablename__ = "attempt_results"

    attempt_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    course_id: Mapped[int] = mapped_column(BigInteger)
    test_kind: Mapped[str] = mapped_column(String(12))
    percent: Mapped[float | None] = mapped_column(Float)
    result: Mapped[str] = mapped_column(String(12))  # passed | failed | invalidated
    revision: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_attempt_results_attempt"),
        Index("ix_attempt_results_user_course", "user_id", "course_id"),
        Index("ix_attempt_results_course_percent", "course_id", "percent"),
    )
