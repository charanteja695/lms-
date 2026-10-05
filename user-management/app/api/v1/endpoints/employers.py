from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentAuth, EmployerServiceDep, OrganizationIdParam, SettingsDep, rate_limit
from app.api.responses import errors
from app.api.v1.endpoints.jobs import JobServiceDep
from app.models.job import JobType
from app.schemas.common import PageContext, SuccessResponse
from app.schemas.employer import (
    EmployerCreate,
    EmployerExportQuery,
    EmployerListItem,
    EmployerListQuery,
    EmployerListResponse,
    EmployerOut,
    EmployerResponse,
    EmployerUpdate,
)
from app.schemas.jobs import JobOut, JobResponse
from app.schemas.user import StatusUpdate
from app.services import export_service

router = APIRouter(prefix="/employers", tags=["Employers"], responses=errors(401))


@router.post(
    "",
    response_model=EmployerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an employer",
    description="Hiring companies for the job portal. Super admins must set `admin_user_id` (an admin with the careers.manage "
    "scope); admins with that scope own the employers they create.",
    responses=errors(403, 409, 422),
)
async def create_employer(
    body: EmployerCreate,
    auth: CurrentAuth,
    service: EmployerServiceDep,
) -> EmployerResponse:
    employer, counts = await service.create_institution(auth.user, body)
    return EmployerResponse(
        message="Employer created successfully.",
        employer=EmployerOut.from_model(employer, counts, auth.user),
    )


@router.get(
    "",
    response_model=EmployerListResponse,
    summary="List employers",
    description="Super admins see all, admins see the employers they own, employer members see their own employer. "
    "`search_text` matches name, code and city.",
    responses=errors(403, 422),
)
async def list_employers(
    query: Annotated[EmployerListQuery, Query()], auth: CurrentAuth, service: EmployerServiceDep
) -> EmployerListResponse:
    items, total, is_exact, counts = await service.list_institutions(auth.user, query)
    return EmployerListResponse(
        message="Employers retrieved successfully.",
        employers=[EmployerListItem.from_model(item, counts.get(item.id, {}), auth.user) for item in items],
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
    summary="Export employers in the background",
    dependencies=[Depends(rate_limit("export", "EXPORT_RATE_LIMIT_PER_HOUR", 3600))],
    responses=errors(401, 403, 422, 429),
    status_code=202,
)
async def create_employer_export_job(
    query: Annotated[EmployerExportQuery, Query()],
    auth: CurrentAuth,
    service: EmployerServiceDep,
    jobs: JobServiceDep,
) -> JobResponse:
    await service.filter_conditions(auth.user, query)
    job = await jobs.create_export_job(auth.user, JobType.EMPLOYER_EXPORT, query)
    return JobResponse(message="Export queued. You will be emailed when it is ready.", job=JobOut.from_model(job))


@router.get(
    "/export",
    response_class=StreamingResponse,
    summary="Export employers (CSV)",
    description="Accepts the same filters as `GET /employers`, including member counts per employer.",
    dependencies=[Depends(rate_limit("export", "EXPORT_RATE_LIMIT_PER_HOUR", 3600))],
    responses={
        200: {
            "description": "CSV file (UTF-8 with BOM), streamed",
            "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
        },
        **errors(401, 403, 422, 429),
    },
)
async def export_employers(
    query: Annotated[EmployerExportQuery, Query()],
    auth: CurrentAuth,
    service: EmployerServiceDep,
    settings: SettingsDep,
    request: Request,
) -> StreamingResponse:
    conditions = await service.prepare_export(auth.user, query)
    stream = export_service.stream_csv(
        request.app.state.sessionmaker,
        export_service.Institution,
        conditions,
        export_service.EMPLOYER_EXPORT_COLUMNS,
        options=export_service.INSTITUTION_EXPORT_OPTIONS,
        max_rows=settings.EXPORT_MAX_ROWS,
        batch_size=settings.EXPORT_BATCH_SIZE,
        extra_loader=export_service.INSTITUTION_COUNTS_LOADER,
    )
    filename = export_service.export_filename("employers")
    return StreamingResponse(
        stream,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{organization_id}",
    response_model=EmployerResponse,
    summary="Get an employer",
    responses=errors(403, 404),
)
async def get_employer(
    organization_id: OrganizationIdParam, auth: CurrentAuth, service: EmployerServiceDep
) -> EmployerResponse:
    employer, counts = await service.get_institution(auth.user, organization_id)
    return EmployerResponse(
        message="Employer retrieved successfully.",
        employer=EmployerOut.from_model(employer, counts, auth.user),
    )


@router.put(
    "/{organization_id}",
    response_model=EmployerResponse,
    summary="Update an employer",
    description="Partial update: only the fields you send are changed. Only super admins can change `admin_user_id`.",
    responses=errors(403, 404, 409, 422),
)
async def update_employer(
    organization_id: OrganizationIdParam,
    body: EmployerUpdate,
    auth: CurrentAuth,
    service: EmployerServiceDep,
) -> EmployerResponse:
    employer, counts = await service.update_institution(auth.user, organization_id, body)
    return EmployerResponse(
        message="Employer updated successfully.",
        employer=EmployerOut.from_model(employer, counts, auth.user),
    )


@router.patch(
    "/{organization_id}/status",
    response_model=EmployerResponse,
    summary="Activate or suspend an employer",
    description="Suspending signs out every employer admin and recruiter immediately.",
    responses=errors(403, 404, 422),
)
async def change_employer_status(
    organization_id: OrganizationIdParam,
    body: StatusUpdate,
    auth: CurrentAuth,
    service: EmployerServiceDep,
) -> EmployerResponse:
    employer, counts = await service.change_status(auth.user, organization_id, body.status, body.reason)
    verb = "suspended" if body.status == "suspended" else "activated"
    return EmployerResponse(
        message=f"Employer {verb} successfully.",
        employer=EmployerOut.from_model(employer, counts, auth.user),
    )


@router.delete(
    "/{organization_id}",
    response_model=SuccessResponse,
    summary="Delete an employer",
    description="Hides the employer and blocks all its members. Records are kept for audit history.",
    responses=errors(403, 404),
)
async def delete_employer(
    organization_id: OrganizationIdParam, auth: CurrentAuth, service: EmployerServiceDep
) -> SuccessResponse:
    await service.delete_institution(auth.user, organization_id)
    return SuccessResponse(message="Employer deleted successfully.")


@router.post(
    "/{organization_id}/revoke",
    response_model=SuccessResponse,
    summary="Sign out every member",
    description="Ends all sessions of everyone in the employer. Accounts stay active.",
    responses=errors(403, 404),
)
async def revoke_employer(
    organization_id: OrganizationIdParam, auth: CurrentAuth, service: EmployerServiceDep
) -> SuccessResponse:
    revoked = await service.revoke_access(auth.user, organization_id)
    return SuccessResponse(message=f"Access revoked. {revoked} active session(s) ended.")
