from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.topic_ref import TopicRef


class TopicItemRef(TimestampMixin, Base):
    __tablename__ = "topic_item_refs"

    topic_item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topic_refs.topic_id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200), default="", server_default="")
    position: Mapped[int]
    item_type: Mapped[str] = mapped_column(String(20))
    required: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    topic: Mapped["TopicRef"] = relationship(back_populates="items", lazy="raise")

    __table_args__ = (Index("ix_topic_item_refs_topic_id_position", "topic_id", "position"),)
