"""Inbound event handlers. ``user.*`` (user-management) keeps the read-model of people: the names an agent sees, and the role
and institution used to check that a ticket is only assigned to someone who may handle it.

  user.created / updated / suspended / activated   {user_id, first_name, last_name, role, status, organization_id}
  user.deleted                                      {user_id}   (the row stays, inactive, so tickets stay readable)
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.config import UserRef


def _int(value: Any) -> int | None:
    try:
        return int(str(value)) if value not in (None, "") else None
    except ValueError:
        return None


async def handle_user_upserted(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    user_id = _int(payload.get("user_id"))
    if user_id is None:
        return
    ref = await db.get(UserRef, user_id)
    if ref is None:
        ref = UserRef(user_id=user_id)
        db.add(ref)
    ref.first_name = str(payload.get("first_name") or "")[:100]
    ref.last_name = str(payload.get("last_name") or "")[:100]
    ref.role = str(payload.get("role") or "")[:20]
    ref.organization_id = _int(payload.get("organization_id"))
    ref.active = payload.get("status", "active") == "active"


async def handle_user_deleted(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    user_id = _int(payload.get("user_id"))
    ref = await db.get(UserRef, user_id) if user_id is not None else None
    if ref is not None:
        ref.active = False
