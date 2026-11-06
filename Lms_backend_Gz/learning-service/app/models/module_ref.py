from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.course_version_ref import CourseVersionRef
    from app.models.topic_ref import TopicRef


class ModuleRef(TimestampMixin, Base):
    __tablename__ = "module_refs"

    module_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    version_id: Mapped[int] = mapped_column(ForeignKey("course_version_refs.version_id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200), default="", server_default="")
    position: Mapped[int]
    pass_mark: Mapped[int]
    module_test_id: Mapped[int | None] = mapped_column(BigInteger)

    course_version: Mapped["CourseVersionRef"] = relationship(back_populates="modules", lazy="raise")
    topics: Mapped[list["TopicRef"]] = relationship(back_populates="module", order_by="TopicRef.position", lazy="raise")

    __table_args__ = (Index("ix_module_refs_version_id_position", "version_id", "position"),)
