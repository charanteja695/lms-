"""Keeps app/models/institution_ref.py in sync with user-management's institutions. Employer
events (``employer.*``) are ignored: employers don't run batches.

  institution.created / institution.updated / institution.suspended / institution.activated
      {"organization_id": "<public id>", "name": ..., "code": ..., "status": ..., ...}
  institution.deleted
      {"organization_id": "<public id>", ...}
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.institution_ref_service import InstitutionRefService


async def handle_institution_upserted(db: AsyncSession, payload: dict[str, Any]) -> None:
    await InstitutionRefService(db).upsert(payload)


async def handle_institution_deleted(db: AsyncSession, payload: dict[str, Any]) -> None:
    await InstitutionRefService(db).mark_deleted(int(payload["organization_id"]))
