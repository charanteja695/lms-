import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.subscription import Subscription


class SeatReservation(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One seat held against a subscription. ``reservation_key`` is caller-supplied (e.g.
    learning-service's enrolment id) so a retried reserve/release call is a no-op instead of
    double-counting — this is the only thing that makes "atomic seat reserve" (docs/PRODUCT.md
    §6.1) safe to call from another service without a distributed transaction."""

    __tablename__ = "seat_reservations"

    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscriptions.id", ondelete="CASCADE"))
    reservation_key: Mapped[str] = mapped_column(String(100))
    released_at: Mapped[datetime | None]

    subscription: Mapped["Subscription"] = relationship(lazy="raise")

    __table_args__ = (
        UniqueConstraint("subscription_id", "reservation_key", name="uq_seat_reservations_subscription_id_key"),
    )
