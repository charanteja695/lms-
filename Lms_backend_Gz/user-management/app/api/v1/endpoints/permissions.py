"""Role- and person-level permissions. The catalog is readable by anyone signed in (labels for the UI);
changing who holds what is a super admin's job."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, CurrentAuth, DbSession, RequestCtx, UserIdParam, require_roles
from app.api.responses import errors
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.permissions.features import PERMISSIONS
from app.permissions.pages import ACTION_LABELS, ACTIONS, MATRIX_ROLES, PAGES
from app.permissions.roles import Role
from app.repositories.user_repository import UserRepository
from app.schemas.permission_admin import (
    ActionOut,
    CatalogEntry,
    CatalogPage,
    CatalogResponse,
    PageAction,
    PermissionChanges,
    PersonPermissions,
    PersonPermissionsResponse,
    RoleMatrixResponse,
    RoleRow,
)
from app.services.permission_service import PermissionService

router = APIRouter(tags=["Permissions"], responses=errors(401, 403))
SuperAdmin = Annotated[AuthContext, Depends(require_roles(Role.SUPER_ADMIN))]


@router.get("/permissions/catalog", response_model=CatalogResponse, summary="Every permission there is")
async def catalog(auth: CurrentAuth) -> CatalogResponse:
    return CatalogResponse(
        message="Permission catalog retrieved successfully.",
        permissions=[
            CatalogEntry(
                key=p.key,
                label=p.label,
                description=p.description,
                modules=list(p.modules),
                audience=p.audience,
                default_roles=sorted(r.value for r in p.default_roles),
            )
            for p in PERMISSIONS
        ],
        actions=[ActionOut(key=a, label=ACTION_LABELS[a]) for a in ACTIONS],
        pages=[
            CatalogPage(
                key=p.key,
                label=p.label,
                group=p.group,
                description=p.description,
                holders=[r.value for r in MATRIX_ROLES if r in p.holders],
                actions=[
                    PageAction(
                        action=a,
                        key=f"{p.key}.{a}",
                        meaning=p.meaning[a],
                        default_roles=[r.value for r in MATRIX_ROLES if r in p.defaults[a]],
                    )
                    for a in p.actions
                ],
            )
            for p in PAGES
        ],
        matrix_roles=[r.value for r in MATRIX_ROLES],
    )


@router.get("/permissions/roles", response_model=RoleMatrixResponse, summary="Each member role's permissions (1/0)")
async def role_matrix(auth: SuperAdmin, db: DbSession) -> RoleMatrixResponse:
    rows = await PermissionService(db).role_matrix()
    return RoleMatrixResponse(
        message="Role permissions retrieved successfully.", roles=[RoleRow.model_validate(r) for r in rows]
    )


@router.put(
    "/permissions/roles/{role}",
    response_model=RoleMatrixResponse,
    summary="Change a role's permissions",
    responses=errors(422),
    description="Applies to everyone with the role. Their open sessions pick it up on their next token refresh (within seconds); nobody is signed out.",
)
async def set_role(
    role: Role, body: PermissionChanges, auth: SuperAdmin, db: DbSession, ctx: RequestCtx
) -> RoleMatrixResponse:
    service = PermissionService(db, ctx)
    await service.set_role(auth.user, role, body.changes)
    return RoleMatrixResponse(
        message="Role permissions saved.", roles=[RoleRow.model_validate(r) for r in await service.role_matrix()]
    )


async def _target(db: DbSession, user_id: int) -> User:
    user = await UserRepository(db).get_by_public_id(user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return user


@router.get(
    "/users/{user_id}/permissions",
    response_model=PersonPermissionsResponse,
    summary="One person's permissions",
    responses=errors(404),
)
async def person(user_id: UserIdParam, auth: SuperAdmin, db: DbSession) -> PersonPermissionsResponse:
    view = await PermissionService(db).user_view(await _target(db, user_id))
    return PersonPermissionsResponse(
        message="Permissions retrieved successfully.", user_permissions=PersonPermissions.model_validate(view)
    )


@router.put(
    "/users/{user_id}/permissions",
    response_model=PersonPermissionsResponse,
    summary="Grant or remove permissions for one person",
    responses=errors(404, 422),
    description="true grants, false removes, null goes back to what their role gives. For an admin this edits their scopes. "
    "Takes effect on their next token refresh (within seconds); they stay signed in.",
)
async def set_person(
    user_id: UserIdParam, body: PermissionChanges, auth: SuperAdmin, db: DbSession, ctx: RequestCtx
) -> PersonPermissionsResponse:
    service = PermissionService(db, ctx)
    target = await _target(db, user_id)
    await service.set_user(auth.user, target, body.changes, body.reason)
    return PersonPermissionsResponse(
        message="Permissions saved.", user_permissions=PersonPermissions.model_validate(await service.user_view(target))
    )
