import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.learning_path import LearningPath


class LearningPathItem(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "learning_path_items"

    learning_path_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("learning_paths.id", ondelete="CASCADE"))
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"))
    position: Mapped[int]

    learning_path: Mapped["LearningPath"] = relationship(back_populates="items", lazy="raise")
    course: Mapped["Course"] = relationship(lazy="raise")

    @property
    def course_public_id(self) -> int:
        return self.course.public_id

    @property
    def title(self) -> str:
        return self.course.title

    @property
    def slug(self) -> str:
        return self.course.slug

    __table_args__ = (
        UniqueConstraint("learning_path_id", "course_id", name="uq_learning_path_items_path_id_course_id"),
        Index("ix_learning_path_items_path_id_position", "learning_path_id", "position"),
    )
