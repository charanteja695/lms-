import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import SubscriptionStatus

if TYPE_CHECKING:
    from app.models.course_ref import CourseRef
    from app.models.institution_ref import InstitutionRef


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Courses x seats x term for one institution (see docs/PRODUCT.md §2). ``seats_used`` is
    an atomic counter reserved/released by learning-service's enrolment flow (see
    app/services/seat_service.py) — this service never tracks *which* student holds a seat."""

    __tablename__ = "subscriptions"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("institution_refs.organization_id", ondelete="RESTRICT"))
    course_id: Mapped[int] = mapped_column(ForeignKey("course_refs.course_id", ondelete="RESTRICT"))
    course_request_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("course_requests.id", ondelete="SET NULL"))

    seats_total: Mapped[int]
    seats_used: Mapped[int] = mapped_column(default=0, server_default="0")
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    status: Mapped[str] = mapped_column(String(20), default=SubscriptionStatus.ACTIVE, server_default=SubscriptionStatus.ACTIVE)

    created_by: Mapped[int] = mapped_column(BigInteger)
    cancelled_at: Mapped[datetime | None]
    cancelled_reason: Mapped[str | None] = mapped_column(String(500))

    institution: Mapped["InstitutionRef"] = relationship(lazy="raise")
    course: Mapped["CourseRef"] = relationship(lazy="raise")

    __table_args__ = (
        Index("ix_subscriptions_organization_id_status", "organization_id", "status"),
        # An institution may hold only one ACTIVE subscription per course at a time (past
        # expired/cancelled subscriptions for the same pair are fine, hence the partial index).
        Index(
            "uq_subscriptions_org_course_one_active",
            "organization_id",
            "course_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )
