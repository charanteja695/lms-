"""What this service consumes from ``lms:events`` (payload contracts of the producers):

  institution.suspended   user-management: {"organization_id"}   -> block further AI spend for that org
  institution.activated   user-management: {"organization_id"}   -> unblock it
  institution.created     user-management: {"organization_id"}   -> upsert not-suspended (the common case)

Nothing else is consumed: ai-gateway does not need course, user or enrolment data to route a completion — the
calling service already resolved all of that before it ever reaches this API. See app/models/refs.py for why
this is the one fact worth tracking.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.refs import OrgStatusRef


async def _upsert(db: AsyncSession, payload: dict[str, Any], *, suspended: bool) -> None:
    organization_id = int(payload["organization_id"])
    ref = await db.get(OrgStatusRef, organization_id)
    if ref is None:
        ref = OrgStatusRef(organization_id=organization_id)
        db.add(ref)
    ref.suspended = suspended


async def handle_institution_suspended(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await _upsert(db, payload, suspended=True)


async def handle_institution_activated(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await _upsert(db, payload, suspended=False)
