import uuid

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class CourseReview(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only audit trail of a course version's lifecycle transitions (submit/approve/
    reject/retire). Never updated or deleted; see app/services/review_service.py."""

    __tablename__ = "reviews"

    course_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_versions.id", ondelete="CASCADE"))
    action: Mapped[str] = mapped_column(String(20))
    actor_user_id: Mapped[int] = mapped_column(BigInteger)
    comment: Mapped[str | None] = mapped_column(String(1000))
