import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType


class OutboxEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Transactional outbox: domain events are written in the same transaction as the change,
    then a relay publishes them to the message broker for other microservices."""

    __tablename__ = "outbox_events"

    event_type: Mapped[str] = mapped_column(String(100))
    aggregate_type: Mapped[str] = mapped_column(String(50))
    aggregate_id: Mapped[uuid.UUID]
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    published_at: Mapped[datetime | None]
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")

    __table_args__ = (
        Index(
            "ix_outbox_events_unpublished",
            "created_at",
            postgresql_where=text("published_at IS NULL"),
            sqlite_where=text("published_at IS NULL"),
        ),
    )
