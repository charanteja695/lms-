from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType


class Notification(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One message for one person: the in-app inbox row. Email copies are ``Delivery`` rows."""

    __tablename__ = "notifications"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    recipient_user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    event_id: Mapped[str] = mapped_column(String(64))
    type_key: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    # Public ids (as strings) the frontend uses to deep-link, e.g. {"enrollment_id": "..."}.
    data: Mapped[dict[str, Any]] = mapped_column(JSONType)
    read_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("event_id", "recipient_user_id", name="uq_notifications_event_recipient"),
        Index("ix_notifications_recipient_created", "recipient_user_id", "created_at"),
        Index(
            "ix_notifications_unread",
            "recipient_user_id",
            postgresql_where=text("read_at IS NULL"),
            sqlite_where=text("read_at IS NULL"),
        ),
    )
