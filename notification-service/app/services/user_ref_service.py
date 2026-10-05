from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import UserStatus
from app.models.user_ref import UserRef

INSTITUTION_HEAD_ROLE = "institution_head"


class UserRefService:
    """Local recipient directory (see app/models/user_ref.py). Only the event consumer writes to
    it; the notification code only reads."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert(self, payload: dict[str, Any]) -> None:
        user_id = int(payload["user_id"])
        organization_id = payload.get("organization_id")
        ref = await self.db.get(UserRef, user_id)
        if ref is None:
            ref = UserRef(user_id=user_id)
            self.db.add(ref)
        ref.organization_id = int(organization_id) if organization_id else None
        ref.role = payload["role"]
        ref.first_name = payload.get("first_name") or ""
        ref.email = payload.get("email") or None
        ref.status = payload.get("status", UserStatus.ACTIVE)

    async def mark_deleted(self, user_id: int) -> None:
        ref = await self.db.get(UserRef, user_id)
        if ref is not None:
            ref.status = UserStatus.DELETED

    async def get(self, user_id: int) -> UserRef | None:
        return await self.db.get(UserRef, user_id)

    async def institution_heads(self, organization_id: int) -> list[UserRef]:
        rows = await self.db.execute(
            select(UserRef).where(
                UserRef.organization_id == organization_id,
                UserRef.role == INSTITUTION_HEAD_ROLE,
                UserRef.status == UserStatus.ACTIVE,
            )
        )
        return list(rows.scalars().all())
