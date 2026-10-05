from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class CourseRef(CreatedAtMixin, Base):
    """Course titles for message wording, from catalog-service's ``course.published`` events.
    One row per published version: enrolment events carry a version id, subscription events a
    course id (resolved to the newest version)."""

    __tablename__ = "course_refs"

    version_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    course_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(300))

    __table_args__ = (Index("ix_course_refs_course_id", "course_id", "created_at"),)
