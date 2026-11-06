"""Read-models built from other services' events (a service never reads another's tables)."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CourseVersionRef(TimestampMixin, Base):
    """From catalog-service's ``course.published`` / ``course.retired``."""

    __tablename__ = "course_version_refs"

    version_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    course_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), default="")
    retired: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_course_version_refs_course", "course_id"),)


class ItemRef(TimestampMixin, Base):
    """One item of a published version's tree: where a chunk came from, so an answer can cite the lesson."""

    __tablename__ = "item_refs"

    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    version_id: Mapped[int] = mapped_column(BigInteger)
    course_id: Mapped[int] = mapped_column(BigInteger)
    module_title: Mapped[str] = mapped_column(String(200), default="")
    topic_title: Mapped[str] = mapped_column(String(200), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    item_type: Mapped[str] = mapped_column(String(20))
    position: Mapped[int] = mapped_column(Integer, default=0)
    media_id: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (Index("ix_item_refs_version", "version_id"), Index("ix_item_refs_media", "media_id"))


class EnrollmentRef(TimestampMixin, Base):
    """From learning-service's ``enrollment.created`` / ``enrollment.removed``: who may ask about which version."""

    __tablename__ = "enrollment_refs"

    enrollment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    student_user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    version_id: Mapped[int] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (Index("ix_enrollment_refs_student", "student_user_id", "active"),)


class AttemptRef(TimestampMixin, Base):
    """From assessment-service's ``attempt.*`` events: whether the student is inside a graded test right now (the
    tutor is disabled there), and the attempt status the support assistant may report back to them."""

    __tablename__ = "attempt_refs"

    attempt_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    test_kind: Mapped[str] = mapped_column(String(20), default="")
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(20))
    deadline_at: Mapped[datetime | None]
    result: Mapped[str | None] = mapped_column(String(20))
    percent: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_attempt_refs_user_state", "user_id", "state"),)


class CertificateRef(TimestampMixin, Base):
    """From certificate-service's ``certificate.issued`` / ``certificate.revoked``."""

    __tablename__ = "certificate_refs"

    certificate_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    student_user_id: Mapped[int] = mapped_column(BigInteger)
    course_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20))
    grade: Mapped[str | None] = mapped_column(String(60))
    issued_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_certificate_refs_student", "student_user_id"),)
