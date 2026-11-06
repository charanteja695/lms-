"""Names-only organisation lookup for platform staff.

``GET /institutions`` and ``/employers`` show an admin only the organisations they own, which is right for
managing them. But an admin whose work spans the platform in another service — analytics (``analytics.view``),
hiring (``careers.manage``), AI, billing, support, exams — still has to pick or name an organisation there
(e.g. "this institution's dashboard"). This gives them id, name, code, city and status, nothing more, and no
way to change anything. Members are refused: they only ever see their own organisation.
"""

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import CurrentAuth, DbSession, OrganizationIdParam
from app.api.responses import errors
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.domain.enums import SortOrder
from app.models.institution import Institution
from app.permissions.roles import OrganizationType, Role
from app.schemas.common import PageContext
from app.schemas.directory import DirectoryEntry, DirectoryEntryResponse, DirectoryQuery, DirectoryResponse

router = APIRouter(prefix="/directory/organizations", tags=["Directory"], responses=errors(401, 403))


def _require_platform_staff(auth: CurrentAuth) -> None:
    if auth.user.role not in {Role.SUPER_ADMIN, Role.ADMIN}:
        raise PermissionDeniedError("Only platform staff can look up other organisations.")


def _entry(org: Institution) -> DirectoryEntry:
    return DirectoryEntry(
        organization_id=org.public_id,
        organization_type=OrganizationType(org.org_type),
        name=org.name,
        code=org.code,
        city=org.city,
        status=org.status,
    )


@router.get(
    "", response_model=DirectoryResponse, summary="Look up organisations by name or code", responses=errors(422)
)
async def list_directory(
    query: Annotated[DirectoryQuery, Query()], auth: CurrentAuth, db: DbSession
) -> DirectoryResponse:
    _require_platform_staff(auth)
    conditions = [Institution.org_type == query.type.value, Institution.deleted_at.is_(None)]
    if query.search_text:
        pattern = f"%{query.search_text.lower()}%"
        conditions.append(func.lower(Institution.name).like(pattern) | func.lower(Institution.code).like(pattern))
    total = (await db.execute(select(func.count()).select_from(Institution).where(*conditions))).scalar_one()
    order = Institution.name.asc() if query.sort_order == SortOrder.ASC else Institution.name.desc()
    rows = (
        await db.execute(
            select(Institution)
            .where(*conditions)
            .order_by(order)
            .offset((query.page - 1) * query.per_page)
            .limit(query.per_page)
        )
    ).scalars()
    return DirectoryResponse(
        message="Organisations retrieved successfully.",
        organizations=[_entry(org) for org in rows],
        page_context=PageContext.build(
            page=query.page,
            per_page=query.per_page,
            total=total,
            is_exact=True,
            sort_column="name",
            sort_order=query.sort_order,
        ),
    )


@router.get(
    "/{organization_id}",
    response_model=DirectoryEntryResponse,
    summary="One organisation's name",
    responses=errors(404),
)
async def get_directory_entry(
    organization_id: OrganizationIdParam, auth: CurrentAuth, db: DbSession
) -> DirectoryEntryResponse:
    _require_platform_staff(auth)
    org = (
        await db.execute(
            select(Institution).where(Institution.public_id == organization_id, Institution.deleted_at.is_(None))
        )
    ).scalar_one_or_none()
    if org is None:
        raise NotFoundError("Organisation not found.")
    return DirectoryEntryResponse(message="Organisation retrieved successfully.", organization=_entry(org))
