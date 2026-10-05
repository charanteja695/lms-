from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Form, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.api import examples
from app.api.deps import (
    CurrentAuth,
    CurrentAuthAllowingPasswordChange,
    SettingsDep,
    UserIdParam,
    UserServiceDep,
    rate_limit,
    user_id_path,
)
from app.api.responses import errors
from app.api.v1.endpoints.jobs import JobServiceDep
from app.core.exceptions import PermissionDeniedError
from app.models.job import JobType
from app.permissions import capabilities, policies
from app.permissions.policies import Action
from app.schemas.common import PageContext, SuccessResponse
from app.schemas.imports import ImportResponse, ImportResultOut
from app.schemas.jobs import JobOut, JobResponse
from app.schemas.permissions import PermissionsOut, PermissionsResponse, UserFormOptionsOut, UserFormOptionsResponse
from app.schemas.user import (
    CredentialsOut,
    MyProfileUpdate,
    SetPasswordRequest,
    StatusUpdate,
    UserCreate,
    UserCreatedResponse,
    UserExportQuery,
    UserListItem,
    UserListQuery,
    UserListResponse,
    UserOut,
    UserResponse,
    UserUpdate,
)
from app.services import export_service
from app.services.import_service import ImportMode, ImportService, template_csv
from app.services.user_service import PreparedUser

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get my profile",
    responses=errors(401),
)
async def get_me(auth: CurrentAuthAllowingPasswordChange, service: UserServiceDep) -> UserResponse:
    user = await service.get_me(auth.user)
    return UserResponse(message="Profile retrieved successfully.", user=UserOut.from_model(user, auth.user))


@router.get(
    "/me/permissions",
    response_model=PermissionsResponse,
    summary="What I can do",
    description="Menu sections, visible and creatable roles, list filters and other rights of the signed-in person. "
    "Clients show screens and buttons from this instead of re-implementing rules; every request is still checked.",
    responses=errors(401),
)
async def my_permissions(auth: CurrentAuth) -> PermissionsResponse:
    return PermissionsResponse(
        message="Permissions retrieved successfully.",
        permissions=PermissionsOut.model_validate(capabilities.my_permissions(auth.user)),
    )


@router.get(
    "/form-options",
    response_model=UserFormOptionsResponse,
    summary="Options for the create/edit user form",
    description="Roles you may choose and, for the chosen `role`, which sections and fields apply and which are required. "
    "Pass `user_id` when editing. Call again when the role changes.",
    responses=errors(401, 404, 422),
)
async def user_form_options(
    auth: CurrentAuth,
    service: UserServiceDep,
    role: Annotated[str | None, Query(description="Role being filled in", examples=["staff"])] = None,
    user_id: Annotated[str | None, Query(description="User being edited")] = None,
) -> UserFormOptionsResponse:
    target = None
    if user_id is not None:
        target = await service.get_user(auth.user, await user_id_path(user_id))
    options = capabilities.user_form_options(auth.user, service.settings, role=role, target=target)
    return UserFormOptionsResponse(
        message="Form options retrieved successfully.", form_options=UserFormOptionsOut.model_validate(options)
    )


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update my contact details",
    description="Users can change their own phone numbers, language, time zone and address. "
    "Names, date of birth and role are managed by their institution.",
    responses=errors(401, 403, 422),
)
async def update_me(body: MyProfileUpdate, auth: CurrentAuth, service: UserServiceDep) -> UserResponse:
    user = await service.update_my_profile(auth.user, body)
    return UserResponse(message="Profile updated successfully.", user=UserOut.from_model(user, auth.user))


@router.post(
    "",
    response_model=UserCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
    description="Create an admin, institution head, staff member or student within your part of the hierarchy. "
    "`credentials` says how the person gets access: an emailed set-up link, the initial password you set, or a "
    "temporary password generated for a student without email (returned only in this response).",
    responses=errors(403, 404, 409, 422),
)
async def create_user(
    body: Annotated[UserCreate, Body(openapi_examples=examples.CREATE_USER)],
    auth: CurrentAuth,
    service: UserServiceDep,
) -> UserCreatedResponse:
    user, prepared = await service.create_user(auth.user, body)
    return UserCreatedResponse(
        message="User created successfully.",
        user=UserOut.from_model(user, auth.user),
        credentials=credentials_out(prepared),
    )


def credentials_out(prepared: PreparedUser) -> CredentialsOut:
    if prepared.password_generated:
        return CredentialsOut(delivery="temporary_password", temporary_password=prepared.password)
    return CredentialsOut(delivery="initial_password" if prepared.password else "email_link")


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users",
    description="Only users you are allowed to see are returned. `search_text` matches name, email, username, "
    "phone, employee code and admission number.",
    responses=errors(401, 403, 422),
)
async def list_users(
    query: Annotated[UserListQuery, Query()], auth: CurrentAuth, service: UserServiceDep
) -> UserListResponse:
    items, total, is_exact = await service.list_users(auth.user, query)
    return UserListResponse(
        message="Users retrieved successfully.",
        users=[UserListItem.from_model(user, auth.user) for user in items],
        page_context=PageContext.build(
            page=query.page,
            per_page=query.per_page,
            total=total,
            is_exact=is_exact,
            sort_column=query.sort_column,
            sort_order=query.sort_order,
        ),
    )


@router.get(
    "/import/template",
    response_class=Response,
    summary="Download the import template (CSV)",
    responses={200: {"description": "CSV template with example rows", "content": {"text/csv": {}}}},
)
async def import_template(auth: CurrentAuth) -> Response:
    return Response(
        content=template_csv().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="user-import-template.csv"'},
    )


@router.post(
    "/import",
    response_model=ImportResponse,
    summary="Import users from CSV",
    description="Upload a CSV based on the template. Each row follows the same rules as `POST /users`. "
    "Use `dry_run=true` to validate first. `mode=all_or_nothing` creates every row or none; "
    "`skip_invalid` creates valid rows and reports the rest. Imported users receive an account set-up email.",
    dependencies=[Depends(rate_limit("import", "IMPORT_RATE_LIMIT_PER_HOUR", 3600))],
    responses=errors(400, 401, 403, 422, 429),
)
async def import_users(
    auth: CurrentAuth,
    service: UserServiceDep,
    file: Annotated[UploadFile, File(description="CSV file (UTF-8)")],
    dry_run: Annotated[bool, Form()] = False,
    mode: Annotated[ImportMode, Form()] = ImportMode.ALL_OR_NOTHING,
) -> ImportResponse:
    if not policies.allowed_target_roles(auth.user.role, Action.CREATE):
        raise PermissionDeniedError("You are not allowed to create users.")
    settings = service.settings
    content = await file.read(settings.IMPORT_MAX_FILE_BYTES + 1)
    result = await ImportService(service).import_users(auth.user, content, dry_run=dry_run, mode=mode)
    if dry_run:
        message = f"Validation finished: {result['valid_rows']} valid, {result['invalid_rows']} invalid row(s)."
    elif result["created"] == 0 and result["errors"]:
        message = "Nothing was imported. Fix the errors and upload again."
    else:
        message = f"Import finished: {result['created']} created, {result['invalid_rows']} failed."
    return ImportResponse(message=message, import_result=ImportResultOut.model_validate(result))


@router.post(
    "/import-jobs",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Import a large CSV in the background",
    description="Same rules and columns as `POST /users/import`, for files up to 50,000 rows. The job appears under "
    "`GET /jobs`; when it completes you are emailed and can download a report with one line per created user "
    "(including temporary passwords for students without email) and per problem.",
    dependencies=[Depends(rate_limit("import", "IMPORT_RATE_LIMIT_PER_HOUR", 3600))],
    responses=errors(400, 401, 403, 422, 429),
)
async def create_import_job(
    auth: CurrentAuth,
    service: UserServiceDep,
    jobs: JobServiceDep,
    file: Annotated[UploadFile, File(description="CSV file (UTF-8)")],
    dry_run: Annotated[bool, Form()] = False,
    mode: Annotated[ImportMode, Form()] = ImportMode.ALL_OR_NOTHING,
) -> JobResponse:
    if not policies.allowed_target_roles(auth.user.role, Action.CREATE):
        raise PermissionDeniedError("You are not allowed to create users.")
    content = await file.read(service.settings.IMPORT_JOB_MAX_FILE_BYTES + 1)
    job = await jobs.create_import_job(auth.user, content, mode=mode.value, dry_run=dry_run)
    return JobResponse(message="Import queued. You will be emailed when it has finished.", job=JobOut.from_model(job))


@router.post(
    "/export-jobs",
    response_model=JobResponse,
    summary="Export users in the background",
    description="For very large exports. Same filters as `GET /users` (query string). Returns a job; "
    "the requester is emailed when the file is ready at `GET /jobs/{job_id}/download`.",
    dependencies=[Depends(rate_limit("export", "EXPORT_RATE_LIMIT_PER_HOUR", 3600))],
    responses=errors(401, 403, 422, 429),
    status_code=202,
)
async def create_user_export_job(
    query: Annotated[UserExportQuery, Query()],
    auth: CurrentAuth,
    service: UserServiceDep,
    jobs: JobServiceDep,
) -> JobResponse:
    await service.filter_conditions(auth.user, query)  # fail fast on filters the caller may not use
    job = await jobs.create_export_job(auth.user, JobType.USER_EXPORT, query)
    return JobResponse(message="Export queued. You will be emailed when it is ready.", job=JobOut.from_model(job))


@router.get(
    "/export",
    response_class=StreamingResponse,
    summary="Export users (CSV)",
    description="Accepts the same filters as `GET /users` and exports every matching user you are allowed to see "
    "(up to EXPORT_MAX_ROWS). Every export is recorded in the audit log.",
    dependencies=[Depends(rate_limit("export", "EXPORT_RATE_LIMIT_PER_HOUR", 3600))],
    responses={
        200: {
            "description": "CSV file (UTF-8 with BOM), streamed",
            "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
        },
        **errors(401, 403, 422, 429),
    },
)
async def export_users(
    query: Annotated[UserExportQuery, Query()],
    auth: CurrentAuth,
    service: UserServiceDep,
    settings: SettingsDep,
    request: Request,
) -> StreamingResponse:
    conditions = await service.prepare_export(auth.user, query)
    return csv_response(request, settings, conditions, "users")


@router.get("/{user_id}", response_model=UserResponse, summary="Get a user", responses=errors(401, 403, 404))
async def get_user(user_id: UserIdParam, auth: CurrentAuth, service: UserServiceDep) -> UserResponse:
    user = await service.get_user(auth.user, user_id)
    return UserResponse(message="User retrieved successfully.", user=UserOut.from_model(user, auth.user))


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user",
    description="Partial update: only the sections and fields you send are changed. Send `null` to clear an "
    "optional value. Changing role or institution signs the user out.",
    responses=errors(401, 403, 404, 409, 422),
)
async def update_user(
    user_id: UserIdParam,
    body: Annotated[UserUpdate, Body(openapi_examples=examples.UPDATE_USER)],
    auth: CurrentAuth,
    service: UserServiceDep,
) -> UserResponse:
    user = await service.update_user(auth.user, user_id, body)
    return UserResponse(message="User updated successfully.", user=UserOut.from_model(user, auth.user))


@router.patch(
    "/{user_id}/status",
    response_model=UserResponse,
    summary="Activate or suspend a user",
    description="A suspended user keeps their data but cannot log in, and is signed out immediately.",
    responses=errors(401, 403, 404, 422),
)
async def change_user_status(
    user_id: UserIdParam, body: StatusUpdate, auth: CurrentAuth, service: UserServiceDep
) -> UserResponse:
    user = await service.change_status(auth.user, user_id, body.status, body.reason)
    verb = "suspended" if body.status == "suspended" else "activated"
    return UserResponse(message=f"User {verb} successfully.", user=UserOut.from_model(user, auth.user))


@router.delete(
    "/{user_id}",
    response_model=SuccessResponse,
    summary="Delete a user",
    description="Deactivates and hides the user permanently. The record is kept for audit history.",
    responses=errors(401, 403, 404, 409),
)
async def delete_user(user_id: UserIdParam, auth: CurrentAuth, service: UserServiceDep) -> SuccessResponse:
    await service.delete_user(auth.user, user_id)
    return SuccessResponse(message="User deleted successfully.")


@router.post(
    "/{user_id}/revoke",
    response_model=SuccessResponse,
    summary="Sign a user out everywhere",
    description="Ends all of the user's sessions immediately. The account stays active and can log in again.",
    responses=errors(401, 403, 404),
)
async def revoke_user(user_id: UserIdParam, auth: CurrentAuth, service: UserServiceDep) -> SuccessResponse:
    revoked = await service.revoke_access(auth.user, user_id)
    return SuccessResponse(message=f"Access revoked. {revoked} active session(s) ended.")


def csv_response(request: Request, settings: SettingsDep, conditions: object, resource: str) -> StreamingResponse:
    stream = export_service.stream_csv(
        request.app.state.sessionmaker,
        export_service.User,
        conditions,  # type: ignore[arg-type]
        export_service.USER_EXPORT_COLUMNS,
        options=export_service.USER_EXPORT_OPTIONS,
        max_rows=settings.EXPORT_MAX_ROWS,
        batch_size=settings.EXPORT_BATCH_SIZE,
    )
    filename = export_service.export_filename(resource)
    return StreamingResponse(
        stream,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{user_id}/password",
    response_model=SuccessResponse,
    summary="Set a temporary password",
    description="For people who cannot use the emailed reset (e.g. students without email). The user must choose a "
    "new password at next sign-in, and all their sessions end.",
    responses=errors(401, 403, 404, 422),
)
async def set_user_password(
    user_id: UserIdParam, body: SetPasswordRequest, auth: CurrentAuth, service: UserServiceDep
) -> SuccessResponse:
    await service.set_password(auth.user, user_id, body.new_password)
    return SuccessResponse(message="Temporary password set. The user must change it at next sign-in.")


@router.post(
    "/{user_id}/mfa/reset",
    response_model=SuccessResponse,
    summary="Reset a user's two-factor authentication",
    description="For a lost or replaced phone. Removes the enrolment and recovery codes and signs the user out.",
    responses=errors(401, 403, 404),
)
async def reset_user_mfa(user_id: UserIdParam, auth: CurrentAuth, service: UserServiceDep) -> SuccessResponse:
    await service.reset_mfa(auth.user, user_id)
    return SuccessResponse(message="Two-factor authentication has been reset. The user must set it up again.")
