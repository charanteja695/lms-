from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.module_ref import ModuleRef
    from app.models.topic_item_ref import TopicItemRef


class TopicRef(TimestampMixin, Base):
    __tablename__ = "topic_refs"

    topic_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    module_id: Mapped[int] = mapped_column(ForeignKey("module_refs.module_id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200), default="", server_default="")
    position: Mapped[int]
    pass_mark: Mapped[int]
    topic_test_id: Mapped[int | None] = mapped_column(BigInteger)

    module: Mapped["ModuleRef"] = relationship(back_populates="topics", lazy="raise")
    items: Mapped[list["TopicItemRef"]] = relationship(
        back_populates="topic", order_by="TopicItemRef.position", lazy="raise"
    )

    __table_args__ = (Index("ix_topic_refs_module_id_position", "module_id", "position"),)
