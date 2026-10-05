from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request, status
from fastapi.responses import StreamingResponse

from app.api import examples
from app.api.deps import (
    AdminIdParam,
    CurrentAuth,
    InstitutionServiceDep,
    SettingsDep,
    UserServiceDep,
    rate_limit,
    require_roles,
)
from app.api.responses import errors
from app.api.v1.endpoints.jobs import JobServiceDep
from app.api.v1.endpoints.users import credentials_out, csv_response
from app.models.job import JobType
from app.models.user import User
from app.permissions.roles import Role
from app.schemas.common import PageContext, SuccessResponse
from app.schemas.jobs import JobOut, JobResponse
from app.schemas.user import (
    AdminCreate,
    AdminCreatedResponse,
    AdminExportQuery,
    AdminListItem,
    AdminListQuery,
    AdminListResponse,
    AdminOut,
    AdminResponse,
    AdminUpdate,
    StatusUpdate,
    UserExportQuery,
    UserListItem,
    UserListQuery,
    UserOut,
)

router = APIRouter(
    prefix="/admins",
    tags=["Admins"],
    dependencies=[Depends(require_roles(Role.SUPER_ADMIN))],
    responses=errors(401, 403),
)


async def _admin_out(user: User, actor: User, institutions: InstitutionServiceDep) -> AdminOut:
    counts = await institutions.institutions.counts_by_type_for_admin(user.id)
    return AdminOut(
        **UserOut.from_model(user, actor).model_dump(),
        institution_count=counts.get("institution", 0),
        employer_count=counts.get("employer", 0),
    )


@router.post(
    "",
    response_model=AdminCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an admin",
    description="Super admins only. Without `account.password`, an account set-up link is emailed.",
    responses=errors(409, 422),
)
async def create_admin(
    body: Annotated[AdminCreate, Body(openapi_examples=examples.CREATE_ADMIN)],
    auth: CurrentAuth,
    service: UserServiceDep,
    institutions: InstitutionServiceDep,
) -> AdminResponse:
    user, prepared = await service.create_user(auth.user, body.to_user_create())
    return AdminCreatedResponse(
        message="Admin created successfully.",
        admin=await _admin_out(user, auth.user, institutions),
        credentials=credentials_out(prepared),
    )


@router.get("", response_model=AdminListResponse, summary="List admins", responses=errors(422))
async def list_admins(
    query: Annotated[AdminListQuery, Query()],
    auth: CurrentAuth,
    service: UserServiceDep,
    institutions: InstitutionServiceDep,
) -> AdminListResponse:
    user_query = query.as_user_filters(UserListQuery)
    items, total, is_exact = await service.list_users(auth.user, user_query, only_role=Role.ADMIN)  # type: ignore[arg-type]
    counts = await institutions.institutions.counts_by_type_for_admins([user.id for user in items])
    return AdminListResponse(
        message="Admins retrieved successfully.",
        admins=[
            AdminListItem(
                **UserListItem.from_model(user, auth.user).model_dump(),
                institution_count=counts.get(user.id, {}).get("institution", 0),
                employer_count=counts.get(user.id, {}).get("employer", 0),
                scopes=list(user.scope_list),
            )
            for user in items
        ],
        page_context=PageContext.build(
            page=query.page,
            per_page=query.per_page,
            total=total,
            is_exact=is_exact,
            sort_column=query.sort_column,
            sort_order=query.sort_order,
        ),
    )


@router.post(
    "/export-jobs",
    response_model=JobResponse,
    summary="Export admins in the background",
    dependencies=[Depends(rate_limit("export", "EXPORT_RATE_LIMIT_PER_HOUR", 3600))],
    responses=errors(401, 403, 422, 429),
    status_code=202,
)
async def create_admin_export_job(
    query: Annotated[AdminExportQuery, Query()],
    auth: CurrentAuth,
    service: UserServiceDep,
    jobs: JobServiceDep,
) -> JobResponse:
    await service.filter_conditions(auth.user, query.as_user_filters(UserExportQuery), only_role=Role.ADMIN)
    job = await jobs.create_export_job(auth.user, JobType.ADMIN_EXPORT, query, only_role=Role.ADMIN)
    return JobResponse(message="Export queued. You will be emailed when it is ready.", job=JobOut.from_model(job))


@router.get(
    "/export",
    response_class=StreamingResponse,
    summary="Export admins (CSV)",
    dependencies=[Depends(rate_limit("export", "EXPORT_RATE_LIMIT_PER_HOUR", 3600))],
    responses={
        200: {
            "description": "CSV file (UTF-8 with BOM), streamed",
            "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
        },
        **errors(401, 403, 422, 429),
    },
)
async def export_admins(
    query: Annotated[AdminExportQuery, Query()],
    auth: CurrentAuth,
    service: UserServiceDep,
    settings: SettingsDep,
    request: Request,
) -> StreamingResponse:
    filters = query.as_user_filters(UserExportQuery)
    conditions = await service.prepare_export(auth.user, filters, only_role=Role.ADMIN)
    return csv_response(request, settings, conditions, "admins")


@router.get("/{user_id}", response_model=AdminResponse, summary="Get an admin", responses=errors(404))
async def get_admin(
    user_id: AdminIdParam, auth: CurrentAuth, service: UserServiceDep, institutions: InstitutionServiceDep
) -> AdminResponse:
    user = await service.get_user(auth.user, user_id, expected_role=Role.ADMIN)
    return AdminResponse(message="Admin retrieved successfully.", admin=await _admin_out(user, auth.user, institutions))


@router.put(
    "/{user_id}",
    response_model=AdminResponse,
    summary="Update an admin",
    description="Partial update: only the sections and fields you send are changed.",
    responses=errors(404, 409, 422),
)
async def update_admin(
    user_id: AdminIdParam,
    body: AdminUpdate,
    auth: CurrentAuth,
    service: UserServiceDep,
    institutions: InstitutionServiceDep,
) -> AdminResponse:
    user = await service.update_user(auth.user, user_id, body.to_user_update(), expected_role=Role.ADMIN)
    return AdminResponse(message="Admin updated successfully.", admin=await _admin_out(user, auth.user, institutions))


@router.patch(
    "/{user_id}/status",
    response_model=AdminResponse,
    summary="Activate or suspend an admin",
    responses=errors(404, 422),
)
async def change_admin_status(
    user_id: AdminIdParam,
    body: StatusUpdate,
    auth: CurrentAuth,
    service: UserServiceDep,
    institutions: InstitutionServiceDep,
) -> AdminResponse:
    user = await service.change_status(auth.user, user_id, body.status, body.reason, expected_role=Role.ADMIN)
    verb = "suspended" if body.status == "suspended" else "activated"
    return AdminResponse(message=f"Admin {verb} successfully.", admin=await _admin_out(user, auth.user, institutions))


@router.delete(
    "/{user_id}",
    response_model=SuccessResponse,
    summary="Delete an admin",
    description="Refused with `ADMIN_HAS_INSTITUTIONS` while the admin still owns institutions.",
    responses=errors(404, 409),
)
async def delete_admin(user_id: AdminIdParam, auth: CurrentAuth, service: UserServiceDep) -> SuccessResponse:
    await service.delete_user(auth.user, user_id, expected_role=Role.ADMIN)
    return SuccessResponse(message="Admin deleted successfully.")


@router.post(
    "/{user_id}/revoke",
    response_model=SuccessResponse,
    summary="Sign an admin out everywhere",
    responses=errors(404),
)
async def revoke_admin(user_id: AdminIdParam, auth: CurrentAuth, service: UserServiceDep) -> SuccessResponse:
    revoked = await service.revoke_access(auth.user, user_id, expected_role=Role.ADMIN)
    return SuccessResponse(message=f"Access revoked. {revoked} active session(s) ended.")


@router.post(
    "/{user_id}/mfa/reset",
    response_model=SuccessResponse,
    summary="Reset an admin's two-factor authentication",
    responses=errors(404),
)
async def reset_admin_mfa(user_id: AdminIdParam, auth: CurrentAuth, service: UserServiceDep) -> SuccessResponse:
    await service.reset_mfa(auth.user, user_id, expected_role=Role.ADMIN)
    return SuccessResponse(message="Two-factor authentication has been reset. The admin must set it up again.")
