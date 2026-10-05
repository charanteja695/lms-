import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.course_version import CourseVersion
    from app.models.topic import Topic


class Module(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A module test (e.g. "JavaScript Fundamentals" module test) unlocks when every topic
    in the module is complete; ``module_test_id`` references a test owned by assessment-service
    (not yet built) and is filled in once that service exists.

    ``position`` orders modules within a version; it is an application-maintained sequence
    (see services/reorder_service.py), not a database-unique constraint, so a bulk reorder
    never has to pass through a temporarily-conflicting state.
    """

    __tablename__ = "modules"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    course_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_versions.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int]
    pass_mark: Mapped[int]
    module_test_id: Mapped[int | None] = mapped_column(BigInteger)

    course_version: Mapped["CourseVersion"] = relationship(back_populates="modules", lazy="raise")
    topics: Mapped[list["Topic"]] = relationship(back_populates="module", order_by="Topic.position", lazy="raise")

    __table_args__ = (Index("ix_modules_course_version_id_position", "course_version_id", "position"),)
