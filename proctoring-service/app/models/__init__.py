"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.case import IntegrityCase
from app.models.outbox_event import OutboxEvent
from app.models.processed_event import ProcessedEvent
from app.models.session import Directive, MediaAccess, ProctorEvent, ProctorSession, Snapshot, TestRef

__all__ = [
    "Base",
    "Directive",
    "IntegrityCase",
    "MediaAccess",
    "OutboxEvent",
    "ProcessedEvent",
    "ProctorEvent",
    "ProctorSession",
    "Snapshot",
    "TestRef",
]
