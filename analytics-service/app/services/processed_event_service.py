from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.processed_event import ProcessedEvent


class ProcessedEventService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def claim(self, event_id: str) -> bool:
        """Record ``event_id`` as handled in the caller's transaction. False means it was already
        handled earlier (a redelivery), so the caller must skip it. If two workers race, the
        primary key makes the second commit fail, which rolls back its side effects too."""
        if await self.db.get(ProcessedEvent, event_id) is not None:
            return False
        self.db.add(ProcessedEvent(event_id=event_id))
        return True

    async def prune(self, *, retention_days: int) -> int:
        result = await self.db.execute(
            delete(ProcessedEvent).where(ProcessedEvent.processed_at < utcnow() - timedelta(days=retention_days))
        )
        await self.db.commit()
        return int(getattr(result, "rowcount", 0) or 0)
