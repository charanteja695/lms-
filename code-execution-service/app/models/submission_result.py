import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class SubmissionResult(UUIDPrimaryKeyMixin, Base):
    """The verdict of one submission on one test case. Only sample cases keep their input, expected and
    actual output (so a student can see why a sample failed); a hidden case keeps the verdict alone."""

    __tablename__ = "submission_results"

    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"))
    test_case_public_id: Mapped[int | None] = mapped_column(BigInteger)
    position: Mapped[int] = mapped_column(Integer)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    weight: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    verdict: Mapped[str] = mapped_column(String(30))
    time_ms: Mapped[int | None] = mapped_column(Integer)
    memory_kb: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(String(500))
    sample_input: Mapped[str | None] = mapped_column(Text)
    sample_expected: Mapped[str | None] = mapped_column(Text)
    sample_actual: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (UniqueConstraint("submission_id", "position", name="uq_submission_results_submission_position"),)
