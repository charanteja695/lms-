import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import DeliveryStatus


class Delivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An external (email) copy of a notification, with its retry state. The rendered subject and
    body are stored so a retry never depends on templates that may have changed since."""

    __tablename__ = "deliveries"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    notification_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"))
    notification_public_id: Mapped[int] = mapped_column(BigInteger)
    recipient_user_id: Mapped[int] = mapped_column(BigInteger)
    channel: Mapped[str] = mapped_column(String(20))
    to_address: Mapped[str] = mapped_column(String(320))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=DeliveryStatus.PENDING, server_default=DeliveryStatus.PENDING)
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    next_attempt_at: Mapped[datetime]
    last_error: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None]

    __table_args__ = (
        Index(
            "ix_deliveries_due",
            "next_attempt_at",
            postgresql_where=text("status = 'pending'"),
            sqlite_where=text("status = 'pending'"),
        ),
        Index("ix_deliveries_status_created", "status", "created_at"),
    )
