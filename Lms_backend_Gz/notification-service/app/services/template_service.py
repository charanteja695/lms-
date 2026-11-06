from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.time import utcnow
from app.db.session import commit_or_conflict
from app.domain.enums import Channel
from app.domain.notification_types import NOTIFICATION_TYPES, NotificationType
from app.models.template_override import TemplateOverride
from app.templates.renderer import validate_template


@dataclass(frozen=True, slots=True)
class TemplateView:
    type_key: str
    category: str
    channel: Channel
    subject: str
    body: str
    default_subject: str
    default_body: str
    variables: tuple[str, ...]
    is_customised: bool
    updated_at: datetime | None


class TemplateService:
    """Wording per notification type and channel: the built-in default unless a super admin has
    saved an override (app/models/template_override.py)."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def get_type(type_key: str) -> NotificationType:
        notification_type = NOTIFICATION_TYPES.get(type_key)
        if notification_type is None:
            raise NotFoundError("Notification type not found.", code="NOTIFICATION_TYPE_NOT_FOUND")
        return notification_type

    async def resolve(self, type_key: str) -> dict[Channel, tuple[str, str]]:
        """``(subject, body)`` to use for each channel right now."""
        notification_type = self.get_type(type_key)
        overrides = await self._overrides_for(type_key)
        return {
            channel: (
                (overrides[channel].subject, overrides[channel].body)
                if channel in overrides
                else (notification_type.subject, notification_type.body)
            )
            for channel in Channel
        }

    async def list_all(self) -> list[TemplateView]:
        overrides = await self._all_overrides()
        return [
            self._view(notification_type, channel, overrides.get((notification_type.key, channel)))
            for notification_type in NOTIFICATION_TYPES.values()
            for channel in Channel
        ]

    async def upsert(self, actor_user_id: int, type_key: str, channel: Channel, *, subject: str, body: str) -> TemplateView:
        notification_type = self.get_type(type_key)
        validate_template(notification_type, subject=subject, body=body)
        override = (await self._overrides_for(type_key)).get(channel)
        if override is None:
            override = TemplateOverride(type_key=type_key, channel=channel)
            self.db.add(override)
        override.subject = subject
        override.body = body
        override.updated_by = actor_user_id
        override.updated_at = utcnow()
        await commit_or_conflict(self.db)
        return self._view(notification_type, channel, override)

    async def reset(self, type_key: str, channel: Channel) -> TemplateView:
        notification_type = self.get_type(type_key)
        await self.db.execute(
            delete(TemplateOverride).where(TemplateOverride.type_key == type_key, TemplateOverride.channel == channel)
        )
        await self.db.commit()
        return self._view(notification_type, channel, None)

    async def _overrides_for(self, type_key: str) -> dict[Channel, TemplateOverride]:
        rows = await self.db.execute(select(TemplateOverride).where(TemplateOverride.type_key == type_key))
        return {Channel(row.channel): row for row in rows.scalars()}

    async def _all_overrides(self) -> dict[tuple[str, Channel], TemplateOverride]:
        rows = await self.db.execute(select(TemplateOverride))
        return {(row.type_key, Channel(row.channel)): row for row in rows.scalars()}

    @staticmethod
    def _view(notification_type: NotificationType, channel: Channel, override: TemplateOverride | None) -> TemplateView:
        return TemplateView(
            type_key=notification_type.key,
            category=notification_type.category,
            channel=channel,
            subject=override.subject if override else notification_type.subject,
            body=override.body if override else notification_type.body,
            default_subject=notification_type.subject,
            default_body=notification_type.body,
            variables=tuple(sorted(notification_type.allowed_variables)),
            is_customised=override is not None,
            updated_at=override.updated_at if override else None,
        )
