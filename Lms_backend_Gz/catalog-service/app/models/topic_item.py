import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.topic import Topic


class TopicItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One learning item inside a topic: a video clip, notes/reading, coding practice or the
    topic's quiz reference. Video items start with ``media_ready=False`` and flip to ``True``
    when this service consumes ``media.ready`` from media-service (see app/events/consumers)."""

    __tablename__ = "topic_items"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    item_type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int]
    required: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    # video items
    media_id: Mapped[int | None] = mapped_column(BigInteger, doc="public clip id from media-service")
    media_ready: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    transcript_ready: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    duration_seconds: Mapped[int | None]

    # notes / practice items
    content_text: Mapped[str | None] = mapped_column(String(20_000))

    topic: Mapped["Topic"] = relationship(back_populates="items", lazy="raise")

    __table_args__ = (Index("ix_topic_items_topic_id_position", "topic_id", "position"),)
