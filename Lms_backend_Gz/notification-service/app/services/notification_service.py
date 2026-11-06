from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.db.types import uuid7
from app.domain.enums import Channel, DeliveryStatus
from app.domain.notification_types import NOTIFICATION_TYPES
from app.models.delivery import Delivery
from app.models.notification import Notification
from app.services.preference_service import PreferenceService
from app.services.template_service import TemplateService
from app.templates.renderer import render


@dataclass(frozen=True, slots=True)
class Recipient:
    user_id: int
    organization_id: int | None
    first_name: str
    email: str | None  # None: in-app only (e.g. a student without an email address)


class NotificationService:
    """Turns one event into inbox rows (always) and email deliveries (when the notification type,
    the recipient's address and their preference allow). Adds rows to the caller's transaction and
    never commits, so the event handler commits them together with its de-duplication record."""

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.preferences = PreferenceService(db)

    async def notify(
        self,
        *,
        event_id: str,
        type_key: str,
        recipients: list[Recipient],
        context: dict[str, str],
        data: dict[str, str],
    ) -> int:
        """``context`` fills the template placeholders, ``data`` is the ids the frontend deep-links with."""
        notification_type = NOTIFICATION_TYPES[type_key]
        templates = await TemplateService(self.db).resolve(type_key)
        in_app_subject, in_app_body = templates[Channel.IN_APP]
        email_subject, email_body = templates[Channel.EMAIL]
        now = utcnow()
        notifications: list[Notification] = []
        deliveries: list[Delivery] = []

        for recipient in recipients:
            variables = {
                **context,
                "first_name": recipient.first_name or "there",
                "app_url": self.settings.FRONTEND_BASE_URL,
            }
            notification = Notification(
                id=uuid7(),
                public_id=new_public_id(),
                recipient_user_id=recipient.user_id,
                organization_id=recipient.organization_id,
                event_id=event_id,
                type_key=type_key,
                category=notification_type.category,
                title=render(in_app_subject, variables),
                body=render(in_app_body, variables),
                data=data,
            )
            notifications.append(notification)

            if (
                notification_type.email
                and recipient.email
                and await self.preferences.email_enabled(recipient.user_id, notification_type.category)
            ):
                deliveries.append(
                    Delivery(
                        public_id=new_public_id(),
                        notification_id=notification.id,
                        notification_public_id=notification.public_id,
                        recipient_user_id=recipient.user_id,
                        channel=Channel.EMAIL,
                        to_address=recipient.email,
                        subject=render(email_subject, variables),
                        body=render(email_body, variables),
                        status=DeliveryStatus.PENDING,
                        next_attempt_at=now,
                    )
                )

        # No ORM relationship links a delivery to its notification, so insert the notifications
        # first or the foreign key fails.
        self.db.add_all(notifications)
        await self.db.flush()
        self.db.add_all(deliveries)
        return len(notifications)
