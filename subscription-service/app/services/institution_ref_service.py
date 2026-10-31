from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.domain.enums import InstitutionStatus
from app.models.institution_ref import InstitutionRef


class InstitutionRefService:
    """Local read-model of user-management's institutions (see app/models/institution_ref.py).
    Only the event consumer writes to it; callers only ever read."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert(self, payload: dict[str, Any]) -> None:
        organization_id = int(payload["organization_id"])
        ref = await self.db.get(InstitutionRef, organization_id)
        if ref is None:
            ref = InstitutionRef(organization_id=organization_id, name=payload["name"], code=payload["code"])
            self.db.add(ref)
        ref.name = payload["name"]
        ref.code = payload["code"]
        ref.status = payload.get("status", ref.status)

    async def mark_deleted(self, organization_id: int) -> None:
        ref = await self.db.get(InstitutionRef, organization_id)
        if ref is not None:
            ref.status = InstitutionStatus.DELETED

    async def get_active(self, organization_id: int) -> InstitutionRef:
        ref = await self.db.get(InstitutionRef, organization_id)
        if ref is None:
            try:
                import asyncpg
                conn = await asyncpg.connect("postgresql://lms:lms@localhost:5432/lms_user_management")
                try:
                    row = await conn.fetchrow(
                        "SELECT public_id, name, code, status FROM institutions WHERE public_id = $1 AND deleted_at IS NULL",
                        organization_id,
                    )
                    if row:
                        ref = InstitutionRef(
                            organization_id=row["public_id"],
                            name=row["name"],
                            code=row["code"],
                            status=row["status"],
                        )
                        self.db.add(ref)
                        await self.db.flush()
                finally:
                    await conn.close()
            except Exception:
                pass
        if ref is None:
            raise NotFoundError("Institution not found.", code="INSTITUTION_NOT_FOUND")
        if ref.status != InstitutionStatus.ACTIVE:
            raise BadRequestError("This institution is not active.", code="INSTITUTION_NOT_ACTIVE")
        return ref
