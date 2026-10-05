"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.config import CannedReply, SlaPolicy, UserRef
from app.models.outbox_event import OutboxEvent
from app.models.processed_event import ProcessedEvent
from app.models.ticket import Ticket, TicketEvent, TicketMessage

__all__ = ["Base", "CannedReply", "OutboxEvent", "ProcessedEvent", "SlaPolicy", "Ticket", "TicketEvent", "TicketMessage", "UserRef"]
