import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TestCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One input/expected-output pair. Both sides are Fernet-encrypted at rest and only ever decrypted
    inside the worker; hidden cases are never sent to a client, samples are shown in the problem."""

    __test__ = False  # not a pytest test class, despite the name
    __tablename__ = "test_cases"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    input_encrypted: Mapped[str] = mapped_column(Text)
    expected_encrypted: Mapped[str] = mapped_column(Text)
    compare_mode: Mapped[str | None] = mapped_column(String(20))  # None: the problem's default
    weight: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    explanation: Mapped[str | None] = mapped_column(Text)  # shown with samples

    __table_args__ = (UniqueConstraint("problem_id", "position", name="uq_test_cases_problem_position"),)
