import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import CourseAccessStatus


class CourseAccess(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One self-registered learner's access to one course, bought from billing-service (``course.purchased``).

    Separate from ``Subscription`` (an institution's seats): a learner's access is theirs alone, never invoiced again here
    (billing already sold it), and a repeat purchase extends ``ends_at`` from whichever is later, now or the current end.
    """

    __tablename__ = "course_access"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger)  # the learner's public user id
    organization_id: Mapped[int] = mapped_column(BigInteger)  # their organisation ("Individual learners")
    course_id: Mapped[int] = mapped_column(BigInteger)
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    status: Mapped[str] = mapped_column(String(10), default=CourseAccessStatus.ACTIVE, server_default=CourseAccessStatus.ACTIVE)

    __table_args__ = (
        Index("uq_course_access_user_course", "user_id", "course_id", unique=True),
        Index("ix_course_access_status_ends_at", "status", "ends_at"),
    )


class CourseAccessPurchase(CreatedAtMixin, Base):
    """Each purchase applied once, whatever the event stream redelivers."""

    __tablename__ = "course_access_purchases"

    purchase_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    access_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course_access.id", ondelete="CASCADE"))
    valid_days: Mapped[int] = mapped_column(Integer)
