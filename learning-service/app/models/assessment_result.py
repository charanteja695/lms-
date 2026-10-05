import uuid

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AssessmentResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The latest released result of one topic/module test for one enrolment, from assessment-service's
    ``attempt.finalized``. ``passed`` is what counts toward completion; ``revision`` orders redelivered and corrected
    announcements (an integrity case can turn a pass into an invalidation later)."""

    __tablename__ = "assessment_results"

    enrollment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrollments.id", ondelete="CASCADE"))
    test_id: Mapped[int] = mapped_column(BigInteger)
    passed: Mapped[bool]
    percent: Mapped[float] = mapped_column(Float)
    attempt_id: Mapped[int] = mapped_column(BigInteger)  # the attempt whose result this is
    revision: Mapped[int] = mapped_column(Integer)

    __table_args__ = (UniqueConstraint("enrollment_id", "test_id", name="uq_assessment_results_enrollment_id_test_id"),)
