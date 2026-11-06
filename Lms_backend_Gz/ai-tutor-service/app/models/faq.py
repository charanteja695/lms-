from typing import Any

from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, NullableJSONType
from app.domain.enums import FaqStatus


class FaqEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A curated question and answer (docs/PRODUCT.md §5.5: staff can promote good answers). A published entry is
    searched before any model is called, and a close-enough match is answered from the entry itself."""

    __tablename__ = "faq_entries"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    scope: Mapped[str] = mapped_column(String(14))
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    question: Mapped[str] = mapped_column(String(500))
    answer: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default=FaqStatus.DRAFT)
    source_message_id: Mapped[int | None] = mapped_column(BigInteger)
    created_by: Mapped[int] = mapped_column(BigInteger)
    published_by: Mapped[int | None] = mapped_column(BigInteger)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding: Mapped[list[float] | None] = mapped_column(NullableJSONType)
    embedding_model: Mapped[str | None] = mapped_column(String(60))
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType)

    __table_args__ = (Index("ix_faq_entries_scope", "status", "scope", "organization_id", "course_id"),)
