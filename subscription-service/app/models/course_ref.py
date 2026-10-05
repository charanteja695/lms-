from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.domain.enums import CourseAvailability


class CourseRef(TimestampMixin, Base):
    """Local read-model of a course, kept in sync from catalog-service's ``course.published``/
    ``course.retired`` outbox events (see app/events/consumers/catalog_events.py). A course can
    only be requested once it has been published at least once (see app/services/course_request_service.py).
    """

    __tablename__ = "course_refs"

    course_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220))
    status: Mapped[str] = mapped_column(String(20), default=CourseAvailability.PUBLISHED, server_default=CourseAvailability.PUBLISHED)
