import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.module import Module
    from app.models.topic_item import TopicItem


class Topic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Topic complete = all required items done + topic test >= pass mark (docs/PRODUCT.md §3.1).
    ``topic_test_id`` references a test owned by assessment-service (not yet built)."""

    __tablename__ = "topics"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int]
    pass_mark: Mapped[int]
    topic_test_id: Mapped[int | None] = mapped_column(BigInteger)

    module: Mapped["Module"] = relationship(back_populates="topics", lazy="raise")
    items: Mapped[list["TopicItem"]] = relationship(back_populates="topic", order_by="TopicItem.position", lazy="raise")

    __table_args__ = (Index("ix_topics_module_id_position", "module_id", "position"),)
