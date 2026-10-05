"""Background jobs (exports, imports): queued by the API, run by ``python -m app.worker``, downloaded by their owner."""

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.context import RequestContext
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.db.types import uuid7
from app.models.job import BackgroundJob, JobStatus, JobType
from app.models.user import User
from app.permissions.roles import Role
from app.schemas.common import FilterQuery
from app.services.audit_service import AuditAction, AuditService
from app.utils.query import paginate


def job_file_path(settings: Settings, job: BackgroundJob) -> Path:
    """The downloadable result: an export, or an import report."""
    return settings.JOB_STORAGE_DIR / f"{job.public_id}.csv"


def job_input_path(settings: Settings, job: BackgroundJob) -> Path:
    """Uploaded file waiting to be imported; deleted once the job has run."""
    return settings.JOB_STORAGE_DIR / f"{job.public_id}.input.csv"


class JobService:
    def __init__(self, db: AsyncSession, settings: Settings, ctx: RequestContext) -> None:
        self.db = db
        self.settings = settings
        self.audit = AuditService(db, ctx)

    async def create_export_job(
        self, actor: User, job_type: JobType, filters: FilterQuery, *, only_role: Role | None = None
    ) -> BackgroundJob:
        """Filters and permissions are validated by the caller before queuing, so bad requests fail fast."""
        parameters: dict[str, Any] = {"filters": filters.model_dump(mode="json", exclude_none=True)}
        if only_role is not None:
            parameters["only_role"] = only_role.value
        job = BackgroundJob(
            id=uuid7(),
            job_type=job_type,
            status=JobStatus.QUEUED,
            requested_by_id=actor.id,
            parameters=parameters,
        )
        self.db.add(job)
        self.audit.log(
            AuditAction.EXPORT_JOB_CREATED,
            actor_id=actor.id,
            resource_type="job",
            resource_id=job.id,
            institution_id=actor.institution_id,
            details={"job_type": job_type, **parameters},
        )
        await self.db.commit()
        return job

    async def create_import_job(self, actor: User, content: bytes, *, mode: str, dry_run: bool) -> BackgroundJob:
        if len(content) > self.settings.IMPORT_JOB_MAX_FILE_BYTES:
            raise BadRequestError(
                f"The file is larger than {self.settings.IMPORT_JOB_MAX_FILE_BYTES // (1024 * 1024)} MB.",
                code="FILE_TOO_LARGE",
            )
        if not content.strip():
            raise BadRequestError("The file has no data rows.", code="EMPTY_FILE")
        job = BackgroundJob(
            id=uuid7(),
            public_id=new_public_id(),
            job_type=JobType.USER_IMPORT,
            status=JobStatus.QUEUED,
            requested_by_id=actor.id,
            parameters={"mode": mode, "dry_run": dry_run},
        )
        path = job_input_path(self.settings, job)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        self.db.add(job)
        self.audit.log(
            AuditAction.IMPORT_JOB_CREATED,
            actor_id=actor.id,
            resource_type="job",
            resource_id=job.id,
            institution_id=actor.institution_id,
            details={"mode": mode, "dry_run": dry_run, "file_size_bytes": len(content)},
        )
        await self.db.commit()
        return job

    async def list_jobs(self, actor: User, *, page: int, per_page: int) -> tuple[list[BackgroundJob], int, bool]:
        stmt = (
            select(BackgroundJob)
            .where(BackgroundJob.requested_by_id == actor.id)
            .order_by(BackgroundJob.created_at.desc(), BackgroundJob.id.desc())
        )
        return await paginate(self.db, stmt, page, per_page)

    async def get_job(self, actor: User, job_id: int) -> BackgroundJob:
        job = (
            await self.db.execute(select(BackgroundJob).where(BackgroundJob.public_id == job_id))
        ).scalar_one_or_none()
        if job is None or job.requested_by_id != actor.id:  # jobs are private to whoever requested them
            raise NotFoundError("Job not found.", code="JOB_NOT_FOUND")
        return job

    async def download_path(self, actor: User, job_id: int) -> tuple[BackgroundJob, Path]:
        job = await self.get_job(actor, job_id)
        now = utcnow()
        if job.status != JobStatus.COMPLETED or (job.expires_at is not None and job.expires_at <= now):
            raise ConflictError("This file is not available for download.", code="JOB_NOT_READY")
        path = job_file_path(self.settings, job)
        if not path.is_file():
            raise ConflictError("This export file has expired.", code="JOB_NOT_READY")
        self.audit.log(AuditAction.EXPORT_DOWNLOADED, actor_id=actor.id, resource_type="job", resource_id=job.id)
        await self.db.commit()
        return job, path
