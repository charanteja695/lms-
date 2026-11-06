from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import ContentStatus

if TYPE_CHECKING:
    from app.models.learning_path_item import LearningPathItem


class LearningPath(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An ordered sequence of courses (e.g. a full-stack track). Uses the same draft ->
    published -> archived lifecycle as a course version, but has no separate versioning:
    editing simply changes ``learning_path_items`` while in draft."""

    __tablename__ = "learning_paths"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default=ContentStatus.DRAFT, server_default=ContentStatus.DRAFT)
    created_by: Mapped[int] = mapped_column(BigInteger)
    published_at: Mapped[datetime | None]
    archived_at: Mapped[datetime | None]

    items: Mapped[list["LearningPathItem"]] = relationship(
        back_populates="learning_path", order_by="LearningPathItem.position", lazy="raise"
    )
