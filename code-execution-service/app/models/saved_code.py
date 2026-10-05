import uuid

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SavedCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A student's work in progress, kept per problem and per language so switching language in the
    editor never loses code (docs/PRODUCT.md §5.2)."""

    __tablename__ = "saved_codes"

    user_id: Mapped[int] = mapped_column(BigInteger)
    problem_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    language_code: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("user_id", "problem_id", "language_code", name="uq_saved_codes_user_problem_language"),
    )
