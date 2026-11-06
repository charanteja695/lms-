from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import CourseRequestStatus

if TYPE_CHECKING:
    from app.models.course_ref import CourseRef
    from app.models.institution_ref import InstitutionRef


class CourseRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An institution head's request for seats on a course (see docs/PRODUCT.md §4:
    "Request courses + seats" -> "Approve -> subscription"). Approving one creates exactly
    one :class:`~app.models.subscription.Subscription`.
    """

    __tablename__ = "course_requests"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("institution_refs.organization_id", ondelete="RESTRICT"))
    course_id: Mapped[int] = mapped_column(ForeignKey("course_refs.course_id", ondelete="RESTRICT"))
    requested_seats: Mapped[int]
    requested_term_days: Mapped[int]
    status: Mapped[str] = mapped_column(
        String(20), default=CourseRequestStatus.SUBMITTED, server_default=CourseRequestStatus.SUBMITTED
    )
    requested_by: Mapped[int] = mapped_column(BigInteger, doc="public user_id of the institution head")
    decided_by: Mapped[int | None] = mapped_column(BigInteger)
    decided_at: Mapped[datetime | None]
    decision_reason: Mapped[str | None] = mapped_column(String(500))

    institution: Mapped["InstitutionRef"] = relationship(lazy="raise")
    course: Mapped["CourseRef"] = relationship(lazy="raise")

    __table_args__ = (
        Index("ix_course_requests_organization_id_status", "organization_id", "status"),
    )
