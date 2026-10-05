from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request, status
from fastapi.responses import StreamingResponse

from app.api import examples
from app.api.deps import CurrentAuth, InstitutionServiceDep, OrganizationIdParam, SettingsDep, rate_limit
from app.api.responses import errors
from app.api.v1.endpoints.jobs import JobServiceDep
from app.models.job import JobType
from app.schemas.common import PageContext, SuccessResponse
from app.schemas.institution import (
    InstitutionCreate,
    InstitutionExportQuery,
    InstitutionListItem,
    InstitutionListQuery,
    InstitutionListResponse,
    InstitutionOut,
    InstitutionResponse,
    InstitutionUpdate,
)
from app.schemas.jobs import JobOut, JobResponse
from app.schemas.user import StatusUpdate
from app.services import export_service

router = APIRouter(prefix="/institutions", tags=["Institutions"], responses=errors(401))


@router.post(
    "",
    response_model=InstitutionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an institution",
    description="Super admins must set `admin_user_id`. Admins always own the institutions they create.",
    responses=errors(403, 409, 422),
)
async def create_institution(
    body: Annotated[InstitutionCreate, Body(openapi_examples=examples.CREATE_INSTITUTION)],
    auth: CurrentAuth,
    service: InstitutionServiceDep,
) -> InstitutionResponse:
    institution, counts = await service.create_institution(auth.user, body)
    return InstitutionResponse(
        message="Institution created successfully.",
        institution=InstitutionOut.from_model(institution, counts, auth.user),
    )


@router.get(
    "",
    response_model=InstitutionListResponse,
    summary="List institutions",
    description="Super admins see all, admins see the institutions they own, members see their own institution. "
    "`search_text` matches name, code and city.",
    responses=errors(403, 422),
)
async def list_institutions(
    query: Annotated[InstitutionListQuery, Query()], auth: CurrentAuth, service: InstitutionServiceDep
) -> InstitutionListResponse:
    items, total, is_exact, counts = await service.list_institutions(auth.user, query)
    return InstitutionListResponse(
        message="Institutions retrieved successfully.",
        institutions=[InstitutionListItem.from_model(item, counts.get(item.id, {}), auth.user) for item in items],
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
    summary="Export institutions in the background",
    dependencies=[Depends(rate_limit("export", "EXPORT_RATE_LIMIT_PER_HOUR", 3600))],
    responses=errors(401, 403, 422, 429),
    status_code=202,
)
async def create_institution_export_job(
    query: Annotated[InstitutionExportQuery, Query()],
    auth: CurrentAuth,
    service: InstitutionServiceDep,
    jobs: JobServiceDep,
) -> JobResponse:
    await service.filter_conditions(auth.user, query)
    job = await jobs.create_export_job(auth.user, JobType.INSTITUTION_EXPORT, query)
    return JobResponse(message="Export queued. You will be emailed when it is ready.", job=JobOut.from_model(job))


@router.get(
    "/export",
    response_class=StreamingResponse,
    summary="Export institutions (CSV)",
    description="Accepts the same filters as `GET /institutions`, including member counts per institution.",
    dependencies=[Depends(rate_limit("export", "EXPORT_RATE_LIMIT_PER_HOUR", 3600))],
    responses={
        200: {
            "description": "CSV file (UTF-8 with BOM), streamed",
            "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}}},
        },
        **errors(401, 403, 422, 429),
    },
)
async def export_institutions(
    query: Annotated[InstitutionExportQuery, Query()],
    auth: CurrentAuth,
    service: InstitutionServiceDep,
    settings: SettingsDep,
    request: Request,
) -> StreamingResponse:
    conditions = await service.prepare_export(auth.user, query)
    stream = export_service.stream_csv(
        request.app.state.sessionmaker,
        export_service.Institution,
        conditions,
        export_service.INSTITUTION_EXPORT_COLUMNS,
        options=export_service.INSTITUTION_EXPORT_OPTIONS,
        max_rows=settings.EXPORT_MAX_ROWS,
        batch_size=settings.EXPORT_BATCH_SIZE,
        extra_loader=export_service.INSTITUTION_COUNTS_LOADER,
    )
    filename = export_service.export_filename("institutions")
    return StreamingResponse(
        stream,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{organization_id}",
    response_model=InstitutionResponse,
    summary="Get an institution",
    responses=errors(403, 404),
)
async def get_institution(
    organization_id: OrganizationIdParam, auth: CurrentAuth, service: InstitutionServiceDep
) -> InstitutionResponse:
    institution, counts = await service.get_institution(auth.user, organization_id)
    return InstitutionResponse(
        message="Institution retrieved successfully.",
        institution=InstitutionOut.from_model(institution, counts, auth.user),
    )


@router.put(
    "/{organization_id}",
    response_model=InstitutionResponse,
    summary="Update an institution",
    description="Partial update: only the fields you send are changed. Only super admins can change `admin_user_id`.",
    responses=errors(403, 404, 409, 422),
)
async def update_institution(
    organization_id: OrganizationIdParam,
    body: InstitutionUpdate,
    auth: CurrentAuth,
    service: InstitutionServiceDep,
) -> InstitutionResponse:
    institution, counts = await service.update_institution(auth.user, organization_id, body)
    return InstitutionResponse(
        message="Institution updated successfully.",
        institution=InstitutionOut.from_model(institution, counts, auth.user),
    )


@router.patch(
    "/{organization_id}/status",
    response_model=InstitutionResponse,
    summary="Activate or suspend an institution",
    description="Suspending signs out every member immediately and blocks their logins.",
    responses=errors(403, 404, 422),
)
async def change_institution_status(
    organization_id: OrganizationIdParam,
    body: StatusUpdate,
    auth: CurrentAuth,
    service: InstitutionServiceDep,
) -> InstitutionResponse:
    institution, counts = await service.change_status(auth.user, organization_id, body.status, body.reason)
    verb = "suspended" if body.status == "suspended" else "activated"
    return InstitutionResponse(
        message=f"Institution {verb} successfully.",
        institution=InstitutionOut.from_model(institution, counts, auth.user),
    )


@router.delete(
    "/{organization_id}",
    response_model=SuccessResponse,
    summary="Delete an institution",
    description="Hides the institution and blocks all its members. Records are kept for audit history.",
    responses=errors(403, 404),
)
async def delete_institution(
    organization_id: OrganizationIdParam, auth: CurrentAuth, service: InstitutionServiceDep
) -> SuccessResponse:
    await service.delete_institution(auth.user, organization_id)
    return SuccessResponse(message="Institution deleted successfully.")


@router.post(
    "/{organization_id}/revoke",
    response_model=SuccessResponse,
    summary="Sign out every member",
    description="Ends all sessions of everyone in the institution. Accounts stay active.",
    responses=errors(403, 404),
)
async def revoke_institution(
    organization_id: OrganizationIdParam, auth: CurrentAuth, service: InstitutionServiceDep
) -> SuccessResponse:
    revoked = await service.revoke_access(auth.user, organization_id)
    return SuccessResponse(message=f"Access revoked. {revoked} active session(s) ended.")
