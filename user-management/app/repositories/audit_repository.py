from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.outbox_event import OutboxEvent


class AuditRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def add_log(self, log: AuditLog) -> None:
        self.db.add(log)

    def add_event(self, event: OutboxEvent) -> None:
        self.db.add(event)
