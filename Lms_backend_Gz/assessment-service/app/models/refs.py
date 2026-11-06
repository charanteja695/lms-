"""Read-models built from other services' events (a service never reads another's tables). They answer one
question: may this student take this test? — from the enrolment and the course structure they are enrolled in."""

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class EnrollmentRef(TimestampMixin, Base):
    """From learning-service's ``enrollment.created`` / ``enrollment.removed`` / ``course.eligible_for_final``."""

    __tablename__ = "enrollment_refs"

    enrollment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    student_user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    version_id: Mapped[int] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    eligible_for_final: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    __table_args__ = (Index("ix_enrollment_refs_student_active", "student_user_id", "active"),)


class VersionRef(TimestampMixin, Base):
    """From catalog-service's ``course.published`` / ``course.retired``: which course a version belongs to."""

    __tablename__ = "version_refs"

    version_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    course_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(12), default="published", server_default="published")


class VersionTarget(Base):
    """Every module and topic of a published version (the tree ``course.published`` carries): a topic or module
    test is open only to students enrolled in a version that contains its target."""

    __tablename__ = "version_targets"

    version_id: Mapped[int] = mapped_column(
        ForeignKey("version_refs.version_id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    target_type: Mapped[str] = mapped_column(String(10), primary_key=True)
    target_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)

    __table_args__ = (Index("ix_version_targets_target", "target_type", "target_id"),)
