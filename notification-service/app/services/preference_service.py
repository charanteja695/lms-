from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationFailedError
from app.db.session import commit_or_conflict
from app.domain.enums import Category
from app.domain.notification_types import CATEGORIES, CATEGORY_INFO
from app.models.notification_preference import NotificationPreference


@dataclass(frozen=True, slots=True)
class PreferenceView:
    category: Category
    label: str
    email_enabled: bool
    email_editable: bool


class PreferenceService:
    """Per-category email choice. Which categories a user may switch off is decided here (the
    frontend only renders ``email_editable``); in-app notifications are always delivered."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_for_user(self, user_id: int) -> list[PreferenceView]:
        chosen = await self._chosen(user_id)
        return [
            PreferenceView(
                category=info.category,
                label=info.label,
                email_enabled=chosen.get(info.category, True) if info.email_editable else True,
                email_editable=info.email_editable,
            )
            for info in CATEGORIES
        ]

    async def update(self, user_id: int, changes: dict[Category, bool]) -> list[PreferenceView]:
        locked = [category for category in changes if not CATEGORY_INFO[category].email_editable]
        if locked:
            raise ValidationFailedError(
                details=[
                    {
                        "field": "preferences",
                        "code": "PREFERENCE_LOCKED",
                        "message": f"Email for {category.value} notifications cannot be changed",
                    }
                    for category in locked
                ]
            )
        existing = {
            row.category: row
            for row in (
                await self.db.execute(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
            ).scalars()
        }
        for category, email_enabled in changes.items():
            row = existing.get(category)
            if row is None:
                self.db.add(NotificationPreference(user_id=user_id, category=category, email_enabled=email_enabled))
            else:
                row.email_enabled = email_enabled
        await commit_or_conflict(self.db)
        return await self.list_for_user(user_id)

    async def email_enabled(self, user_id: int, category: Category) -> bool:
        if not CATEGORY_INFO[category].email_editable:
            return True
        return (await self._chosen(user_id)).get(category, True)

    async def _chosen(self, user_id: int) -> dict[Category, bool]:
        rows = await self.db.execute(
            select(NotificationPreference.category, NotificationPreference.email_enabled).where(
                NotificationPreference.user_id == user_id
            )
        )
        return {Category(category): enabled for category, enabled in rows.all()}
