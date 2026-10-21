"""The organisation tree: super admin -> admins -> institutions -> head -> staff and students (counts).

What each person sees is their own part of it: the super admin everything, an admin the institutions they own, an
institution's members their own institution. One request, a handful of grouped queries — no per-node round trips.
"""

import uuid
from collections import defaultdict

from fastapi import APIRouter
from pydantic import Field
from sqlalchemy import func, select

from app.api.deps import CurrentAuth, DbSession
from app.api.responses import errors
from app.core.exceptions import PermissionDeniedError
from app.models.academics import Department
from app.models.institution import Institution
from app.models.user import User
from app.permissions.roles import OrganizationType, Role, UserStatus
from app.schemas.common import ResponseSchema, SuccessResponse
from app.schemas.types import PublicIdOut

router = APIRouter(tags=["Organisation tree"], responses=errors(401, 403))


class PersonNode(ResponseSchema):
    user_id: PublicIdOut
    full_name: str
    status: str


class InstitutionNode(ResponseSchema):
    organization_id: PublicIdOut
    name: str
    code: str
    status: str
    city: str
    heads: list[PersonNode]
    staff: int
    students: int
    departments: int


class AdminNode(ResponseSchema):
    admin: PersonNode | None = Field(description="null for institutions the super admin holds directly")
    institutions: list[InstitutionNode]


class HierarchyOut(ResponseSchema):
    super_admins: list[PersonNode]
    admins: list[AdminNode]
    totals: dict[str, int]


class HierarchyResponse(SuccessResponse):
    hierarchy: HierarchyOut


def _person(user: User) -> PersonNode:
    return PersonNode(user_id=user.public_id, full_name=user.full_name, status=user.status)


@router.get(
    "/hierarchy",
    response_model=HierarchyResponse,
    summary="Super admin -> admins -> institutions -> head -> staff and students",
)
async def hierarchy(auth: CurrentAuth, db: DbSession) -> HierarchyResponse:
    actor = auth.user
    scope = select(Institution).where(
        Institution.org_type == OrganizationType.INSTITUTION, Institution.deleted_at.is_(None)
    )
    if actor.role == Role.ADMIN:
        scope = scope.where(Institution.admin_id == actor.id)
    elif actor.role != Role.SUPER_ADMIN:
        if actor.institution_id is None or actor.role not in (Role.INSTITUTION_HEAD, Role.STAFF):
            raise PermissionDeniedError("Only staff and above see the organisation tree.")
        scope = scope.where(Institution.id == actor.institution_id)
    institutions = list((await db.execute(scope.order_by(Institution.name))).scalars())
    ids = [i.id for i in institutions]

    counts: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    heads: dict[uuid.UUID, list[User]] = defaultdict(list)
    departments: dict[uuid.UUID, int] = {}
    if ids:
        for institution_id, role, count in (
            await db.execute(
                select(User.institution_id, User.role, func.count())
                .where(User.institution_id.in_(ids), User.deleted_at.is_(None))
                .group_by(User.institution_id, User.role)
            )
        ).tuples():
            if institution_id is not None:
                counts[institution_id][role] = int(count)
        for head in (
            await db.execute(
                select(User)
                .where(User.institution_id.in_(ids), User.role == Role.INSTITUTION_HEAD, User.deleted_at.is_(None))
                .order_by(User.first_name)
            )
        ).scalars():
            if head.institution_id is not None:
                heads[head.institution_id].append(head)
        departments = {
            k: int(v)
            for k, v in (
                await db.execute(
                    select(Department.institution_id, func.count())
                    .where(Department.institution_id.in_(ids))
                    .group_by(Department.institution_id)
                )
            ).tuples()
        }

    admin_ids = {i.admin_id for i in institutions}
    if actor.role == Role.SUPER_ADMIN:  # admins with no institutions yet still belong in the tree
        admin_ids |= set(
            (await db.execute(select(User.id).where(User.role == Role.ADMIN, User.deleted_at.is_(None)))).scalars()
        )
    people = (
        {u.id: u for u in (await db.execute(select(User).where(User.id.in_(admin_ids)))).scalars()} if admin_ids else {}
    )

    grouped: dict[uuid.UUID, list[InstitutionNode]] = defaultdict(list)
    for institution in institutions:
        c = counts.get(institution.id, {})
        grouped[institution.admin_id].append(
            InstitutionNode(
                organization_id=institution.public_id,
                name=institution.name,
                code=institution.code,
                status=institution.status,
                city=institution.city,
                heads=[_person(h) for h in heads.get(institution.id, [])],
                staff=c.get(Role.STAFF, 0),
                students=c.get(Role.STUDENT, 0),
                departments=departments.get(institution.id, 0),
            )
        )
    admins: list[AdminNode] = []
    for admin_id in sorted(admin_ids, key=lambda i: people[i].full_name.lower() if i in people else ""):
        person = people.get(admin_id)
        is_admin = person is not None and person.role == Role.ADMIN
        admins.append(
            AdminNode(admin=_person(person) if is_admin and person else None, institutions=grouped.get(admin_id, []))
        )

    super_admins: list[PersonNode] = []
    if actor.role == Role.SUPER_ADMIN:
        super_admins = [
            _person(u)
            for u in (
                await db.execute(
                    select(User).where(
                        User.role == Role.SUPER_ADMIN, User.status == UserStatus.ACTIVE, User.deleted_at.is_(None)
                    )
                )
            ).scalars()
        ]
    return HierarchyResponse(
        message="Organisation tree retrieved successfully.",
        hierarchy=HierarchyOut(
            super_admins=super_admins,
            admins=admins,
            totals={
                "admins": sum(1 for a in admins if a.admin),
                "institutions": len(institutions),
                "staff": sum(c.get(Role.STAFF, 0) for c in counts.values()),
                "students": sum(c.get(Role.STUDENT, 0) for c in counts.values()),
            },
        ),
    )
