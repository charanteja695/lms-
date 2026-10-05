from lms_common.pagination import paginate
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.time import utcnow
from app.models.notification import Notification
from app.schemas.common import InboxQuery


class InboxService:
    """A user's own notifications. Every query is scoped to ``user_id`` from the token, so another
    user's notification is indistinguishable from one that does not exist."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_user(self, user_id: int, query: InboxQuery) -> tuple[list[Notification], int, bool]:
        stmt = select(Notification).where(Notification.recipient_user_id == user_id)
        if query.unread:
            stmt = stmt.where(Notification.read_at.is_(None))
        stmt = stmt.order_by(
            Notification.created_at.desc() if query.sort_order == "desc" else Notification.created_at.asc(),
            Notification.id,
        )
        return await paginate(self.db, stmt, query.page, query.per_page)

    async def unread_count(self, user_id: int) -> int:
        return int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(Notification)
                    .where(Notification.recipient_user_id == user_id, Notification.read_at.is_(None))
                )
            ).scalar_one()
        )

    async def mark_read(self, user_id: int, notification_id: int) -> Notification:
        notification = (
            await self.db.execute(
                select(Notification).where(
                    Notification.public_id == notification_id, Notification.recipient_user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if notification is None:
            raise NotFoundError("Notification not found.", code="NOTIFICATION_NOT_FOUND")
        if notification.read_at is None:  # idempotent: keep the first read time
            notification.read_at = utcnow()
            await self.db.commit()
        return notification

    async def mark_all_read(self, user_id: int) -> int:
        result = await self.db.execute(
            update(Notification)
            .where(Notification.recipient_user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=utcnow())
        )
        await self.db.commit()
        return int(getattr(result, "rowcount", 0) or 0)
