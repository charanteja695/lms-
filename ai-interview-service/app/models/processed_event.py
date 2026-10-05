from datetime import datetime

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utcnow
from app.db.base import Base


class ProcessedEvent(Base):
    """De-duplication ledger for ``lms:events``: delivery is at-least-once, and a repeated event
    must never flip a status twice. Written in the same transaction as the handler's effects,
    so an event is either fully processed and recorded or neither. Pruned by the worker."""

    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(default=utcnow)

    __table_args__ = (Index("ix_processed_events_processed_at", "processed_at"),)
