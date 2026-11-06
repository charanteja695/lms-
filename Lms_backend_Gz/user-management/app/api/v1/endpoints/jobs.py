from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import FileResponse

from app.api.deps import CurrentAuth, DbSession, RequestCtx, SettingsDep
from app.api.responses import errors
from app.core.exceptions import NotFoundError
from app.core.ids import EXAMPLE_USER_ID, parse_public_id
from app.domain.enums import SortOrder
from app.schemas.common import PageContext
from app.schemas.jobs import JobListQuery, JobListResponse, JobOut, JobResponse
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["Jobs"], responses=errors(401, 403))


def get_job_service(db: DbSession, settings: SettingsDep, ctx: RequestCtx) -> JobService:
    return JobService(db, settings, ctx)


JobServiceDep = Annotated[JobService, Depends(get_job_service)]


async def job_id_path(job_id: Annotated[str, Path(examples=[EXAMPLE_USER_ID])]) -> int:
    number = parse_public_id(job_id)
    if number is None:
        raise NotFoundError("Job not found.", code="JOB_NOT_FOUND")
    return number


JobIdParam = Annotated[int, Depends(job_id_path)]


@router.get("", response_model=JobListResponse, summary="List my background jobs", responses=errors(422))
async def list_jobs(
    query: Annotated[JobListQuery, Query()], auth: CurrentAuth, service: JobServiceDep
) -> JobListResponse:
    items, total, is_exact = await service.list_jobs(auth.user, page=query.page, per_page=query.per_page)
    return JobListResponse(
        message="Jobs retrieved successfully.",
        jobs=[JobOut.from_model(job) for job in items],
        page_context=PageContext.build(
            page=query.page,
            per_page=query.per_page,
            total=total,
            is_exact=is_exact,
            sort_column="created_time",
            sort_order=SortOrder.DESC,
        ),
    )


@router.get("/{job_id}", response_model=JobResponse, summary="Get a job's status", responses=errors(404))
async def get_job(job_id: JobIdParam, auth: CurrentAuth, service: JobServiceDep) -> JobResponse:
    job = await service.get_job(auth.user, job_id)
    return JobResponse(message="Job retrieved successfully.", job=JobOut.from_model(job))


@router.get(
    "/{job_id}/download",
    response_class=FileResponse,
    summary="Download a completed export",
    description="Only the person who requested the export can download it, until `expires_time`.",
    responses={200: {"content": {"text/csv": {}}, "description": "CSV file"}, **errors(404, 409)},
)
async def download_job(job_id: JobIdParam, auth: CurrentAuth, service: JobServiceDep) -> FileResponse:
    job, path = await service.download_path(auth.user, job_id)
    return FileResponse(
        path, media_type="text/csv; charset=utf-8", filename=job.file_name or f"export-{job.public_id}.csv"
    )
