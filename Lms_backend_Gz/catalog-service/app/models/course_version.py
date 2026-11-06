import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import ContentStatus

if TYPE_CHECKING:
    from app.models.course import Course
    from app.models.course_rule import CourseRule
    from app.models.module import Module


class CourseVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One immutable-once-published snapshot of a course's content (see docs/PRODUCT.md §3.2).

    A new draft is never created by mutating a published version: authoring always happens
    on the row still in ``draft``, and publishing freezes it (see services/version_service.py).
    """

    __tablename__ = "course_versions"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    version_number: Mapped[int]
    status: Mapped[str] = mapped_column(String(20), default=ContentStatus.DRAFT, server_default=ContentStatus.DRAFT)

    created_by: Mapped[int] = mapped_column(BigInteger)
    submitted_at: Mapped[datetime | None]
    submitted_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None]
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)
    reject_reason: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None]
    retired_at: Mapped[datetime | None]

    course: Mapped["Course"] = relationship(back_populates="versions", lazy="raise")
    modules: Mapped[list["Module"]] = relationship(
        back_populates="course_version", order_by="Module.position", lazy="raise"
    )
    rule: Mapped["CourseRule"] = relationship(back_populates="course_version", lazy="raise", uselist=False)

    __table_args__ = (
        UniqueConstraint("course_id", "version_number", name="uq_course_versions_course_id_version_number"),
        Index("ix_course_versions_course_id_status", "course_id", "status"),
    )
