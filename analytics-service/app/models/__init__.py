"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.fact import DailyRollup, EnrollmentRef, EventFact
from app.models.outbox_event import OutboxEvent
from app.models.processed_event import ProcessedEvent
from app.models.report import ReportDefinition, ReportRun

__all__ = [
    "Base",
    "DailyRollup",
    "EnrollmentRef",
    "EventFact",
    "OutboxEvent",
    "ProcessedEvent",
    "ReportDefinition",
    "ReportRun",
]
