from typing import Self

from pydantic import Field

from app.core.config import get_settings
from app.models.job import BackgroundJob, JobStatus, JobType
from app.schemas.common import ListQuery, PageContext, ResponseSchema, SuccessResponse
from app.schemas.types import PublicIdOut, Timestamp


class ImportSummaryOut(ResponseSchema):
    dry_run: bool
    mode: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    created: int


class JobOut(ResponseSchema):
    job_id: PublicIdOut
    type: JobType
    status: JobStatus = Field(description="queued, running, completed, failed or expired")
    row_count: int | None
    file_name: str | None
    file_size_bytes: int | None
    error_message: str | None
    download_url: str | None = Field(description="Relative API path, present once completed (export or import report)")
    import_summary: ImportSummaryOut | None = Field(default=None, description="Import jobs only, once completed")
    created_time: Timestamp
    started_time: Timestamp | None
    finished_time: Timestamp | None
    expires_time: Timestamp | None

    @classmethod
    def from_model(cls, job: BackgroundJob) -> Self:
        prefix = get_settings().API_V1_PREFIX
        return cls(
            job_id=job.public_id,
            type=JobType(job.job_type),
            status=JobStatus(job.status),
            row_count=job.row_count,
            file_name=job.file_name,
            file_size_bytes=job.file_size_bytes,
            error_message=job.error_message,
            download_url=f"{prefix}/jobs/{job.public_id}/download" if job.status == JobStatus.COMPLETED else None,
            import_summary=ImportSummaryOut.model_validate(job.result) if job.result else None,
            created_time=job.created_at,
            started_time=job.started_at,
            finished_time=job.finished_at,
            expires_time=job.expires_at,
        )


class JobResponse(SuccessResponse):
    job: JobOut


class JobListQuery(ListQuery):
    pass


class JobListResponse(SuccessResponse):
    jobs: list[JobOut]
    page_context: PageContext
