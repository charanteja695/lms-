import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import ColumnElement, Select, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.institution import Institution
from app.models.user import User
from app.utils.query import paginate

INSTITUTION_DETAIL_OPTIONS = (joinedload(Institution.admin), joinedload(Institution.created_by))
INSTITUTION_LIST_OPTIONS = (joinedload(Institution.admin),)


class InstitutionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, institution_id: uuid.UUID, *, include_deleted: bool = False) -> Institution | None:
        institution = await self.db.get(Institution, institution_id)
        if institution is None or (institution.deleted_at is not None and not include_deleted):
            return None
        return institution

    async def get_by_public_id(
        self, public_id: int, *, include_deleted: bool = False, detailed: bool = False
    ) -> Institution | None:
        stmt = select(Institution).where(Institution.public_id == public_id)
        if detailed:
            stmt = stmt.options(*INSTITUTION_DETAIL_OPTIONS).execution_options(populate_existing=True)
        institution = (await self.db.execute(stmt)).unique().scalar_one_or_none()
        if institution is None or (institution.deleted_at is not None and not include_deleted):
            return None
        return institution

    async def get_detailed(self, institution_id: uuid.UUID) -> Institution:
        stmt = (
            select(Institution)
            .where(Institution.id == institution_id)
            .options(*INSTITUTION_DETAIL_OPTIONS)
            .execution_options(populate_existing=True)
        )
        return (await self.db.execute(stmt)).unique().scalar_one()

    async def code_taken(self, code: str, *, exclude_id: uuid.UUID | None = None) -> bool:
        conditions = [Institution.code == code.upper(), Institution.deleted_at.is_(None)]
        if exclude_id is not None:
            conditions.append(Institution.id != exclude_id)
        return bool((await self.db.execute(select(exists().where(*conditions)))).scalar())

    async def counts_by_type_for_admin(self, admin_id: uuid.UUID) -> dict[str, int]:
        stmt = (
            select(Institution.org_type, func.count())
            .where(Institution.admin_id == admin_id, Institution.deleted_at.is_(None))
            .group_by(Institution.org_type)
        )
        return {org_type: int(count) for org_type, count in (await self.db.execute(stmt)).all()}

    async def counts_by_type_for_admins(self, admin_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
        counts: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
        if not admin_ids:
            return counts
        stmt = (
            select(Institution.admin_id, Institution.org_type, func.count())
            .where(Institution.admin_id.in_(admin_ids), Institution.deleted_at.is_(None))
            .group_by(Institution.admin_id, Institution.org_type)
        )
        for admin_id, org_type, count in (await self.db.execute(stmt)).all():
            counts[admin_id][org_type] = int(count)
        return counts

    async def count_for_admin(self, admin_id: uuid.UUID) -> int:
        return (await self.counts_for_admins([admin_id])).get(admin_id, 0)

    async def counts_for_admins(self, admin_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not admin_ids:
            return {}
        stmt = (
            select(Institution.admin_id, func.count())
            .where(Institution.admin_id.in_(admin_ids), Institution.deleted_at.is_(None))
            .group_by(Institution.admin_id)
        )
        return {admin_id: int(count) for admin_id, count in (await self.db.execute(stmt)).all()}

    async def member_counts(self, institution_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, int]]:
        """Non-deleted members per institution, grouped by role, in one query."""
        counts: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
        if not institution_ids:
            return counts
        stmt = (
            select(User.institution_id, User.role, func.count())
            .where(User.institution_id.in_(institution_ids), User.deleted_at.is_(None))
            .group_by(User.institution_id, User.role)
        )
        for institution_id, role, count in (await self.db.execute(stmt)).all():
            counts[institution_id][role] = int(count)
        return counts

    @staticmethod
    def ids_owned_by_admin(admin_id: uuid.UUID) -> Select[tuple[uuid.UUID]]:
        return select(Institution.id).where(Institution.admin_id == admin_id, Institution.deleted_at.is_(None))

    async def list(
        self, conditions: list[ColumnElement[bool]], *, order_by: list[Any], page: int, per_page: int
    ) -> tuple[list[Institution], int, bool]:
        stmt = select(Institution).where(*conditions).order_by(*order_by)
        return await paginate(self.db, stmt, page, per_page, options=INSTITUTION_LIST_OPTIONS)

    def add(self, institution: Institution) -> None:
        self.db.add(institution)

    @staticmethod
    def event_payload(institution: Institution, *, admin_public_id: int) -> dict[str, Any]:
        return {
            "organization_id": str(institution.public_id),
            "name": institution.name,
            "code": institution.code,
            "organization_type": institution.org_type,
            "type": institution.institution_type,
            "industry": institution.industry,
            "admin_user_id": str(admin_public_id),
            "status": institution.status,
            "timezone": institution.timezone,
        }
