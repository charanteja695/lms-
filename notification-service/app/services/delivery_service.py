import logging
from datetime import timedelta

from lms_common.pagination import paginate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.email import EmailMessage, EmailSender, html_from_text
from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.time import utcnow
from app.domain.enums import DeliveryStatus
from app.models.delivery import Delivery
from app.schemas.common import DeliveryQuery
from app.services.outbox import write_event

logger = logging.getLogger(__name__)


class DeliveryService:
    """Sends pending email deliveries and keeps their retry state; also the super admin's view of them."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------ worker side

    async def claim_due(self) -> list[Delivery]:
        """Take a batch of due deliveries. Claiming pushes ``next_attempt_at`` out by the lease and
        commits, so other workers skip them and no row lock is held while SMTP is slow; if this
        worker dies mid-send, the lease expires and the delivery is retried."""
        now = utcnow()
        due = list(
            (
                await self.db.execute(
                    select(Delivery)
                    .where(Delivery.status == DeliveryStatus.PENDING, Delivery.next_attempt_at <= now)
                    .order_by(Delivery.next_attempt_at)
                    .limit(self.settings.DELIVERY_BATCH_SIZE)
                    .with_for_update(skip_locked=True)
                )
            ).scalars()
        )
        for delivery in due:
            delivery.next_attempt_at = now + timedelta(seconds=self.settings.DELIVERY_CLAIM_LEASE_SECONDS)
        await self.db.commit()
        return due

    async def attempt(self, delivery: Delivery, sender: EmailSender) -> None:
        """One send attempt: mark it sent, schedule a retry, or give up after DELIVERY_MAX_ATTEMPTS."""
        try:
            await sender.send(
                EmailMessage(
                    to=delivery.to_address,
                    subject=delivery.subject,
                    text_body=delivery.body,
                    html_body=html_from_text(delivery.body),
                )
            )
        except Exception as exc:
            logger.warning("Email delivery failed", extra={"extra_fields": {"delivery": str(delivery.public_id)}}, exc_info=True)
            self._record_failure(delivery, f"{type(exc).__name__}: {exc}"[:500])
        else:
            delivery.status = DeliveryStatus.SENT
            delivery.attempts += 1
            delivery.sent_at = utcnow()
            delivery.last_error = None
            self._emit("notification.delivered", delivery)
        await self.db.commit()

    def _record_failure(self, delivery: Delivery, error: str) -> None:
        delivery.attempts += 1
        delivery.last_error = error
        if delivery.attempts >= self.settings.DELIVERY_MAX_ATTEMPTS:
            delivery.status = DeliveryStatus.FAILED
            self._emit("notification.failed", delivery)
            return
        backoff = min(
            self.settings.DELIVERY_RETRY_BASE_SECONDS * 2 ** (delivery.attempts - 1),
            self.settings.DELIVERY_RETRY_MAX_SECONDS,
        )
        delivery.next_attempt_at = utcnow() + timedelta(seconds=backoff)

    def _emit(self, event_type: str, delivery: Delivery) -> None:
        payload = {
            "delivery_id": str(delivery.public_id),
            "notification_id": str(delivery.notification_public_id),
            "user_id": str(delivery.recipient_user_id),
            "channel": delivery.channel,
        }
        if event_type == "notification.failed":
            payload["attempts"] = str(delivery.attempts)
        write_event(self.db, event_type=event_type, aggregate_id=delivery.id, payload=payload)

    # ------------------------------------------------------------------ super admin side

    async def list_deliveries(self, query: DeliveryQuery) -> tuple[list[Delivery], int, bool]:
        stmt = select(Delivery)
        if query.status:
            stmt = stmt.where(Delivery.status == query.status)
        stmt = stmt.order_by(
            Delivery.created_at.desc() if query.sort_order == "desc" else Delivery.created_at.asc(), Delivery.id
        )
        return await paginate(self.db, stmt, query.page, query.per_page)

    async def retry(self, delivery_id: int) -> Delivery:
        delivery = (await self.db.execute(select(Delivery).where(Delivery.public_id == delivery_id))).scalar_one_or_none()
        if delivery is None:
            raise NotFoundError("Delivery not found.", code="DELIVERY_NOT_FOUND")
        if delivery.status != DeliveryStatus.FAILED:
            raise BadRequestError("Only a failed delivery can be retried.", code="DELIVERY_NOT_FAILED")
        delivery.status = DeliveryStatus.PENDING
        delivery.attempts = 0
        delivery.last_error = None
        delivery.next_attempt_at = utcnow()
        await self.db.commit()
        return delivery


async def deliver_due(sessionmaker: async_sessionmaker[AsyncSession], sender: EmailSender, settings: Settings) -> int:
    """Worker entry point: one sweep over the due deliveries. Returns how many it attempted."""
    async with sessionmaker() as db:
        service = DeliveryService(db, settings)
        due = await service.claim_due()
        for delivery in due:
            await service.attempt(delivery, sender)
        return len(due)
