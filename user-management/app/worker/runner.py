"""Background worker: export jobs, event relay and housekeeping.

Run one or more instances with ``python -m app.worker``. Jobs are claimed with
``SELECT ... FOR UPDATE SKIP LOCKED``, so instances never pick the same job.
"""

import asyncio
import csv
import logging
import os
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli.maintenance import purge_expired
from app.core.config import Settings
from app.core.context import RequestContext
from app.core.exceptions import AppError
from app.core.time import utcnow
from app.events.publisher import RedisStreamPublisher, relay_outbox
from app.models.job import BackgroundJob, JobStatus, JobType
from app.models.user import User
from app.notifications.email import EmailSender
from app.notifications.notifier import Notifier
from app.permissions.policies import Action
from app.permissions.roles import OrganizationType, Role
from app.repositories.institution_repository import InstitutionRepository
from app.schemas.employer import EmployerExportQuery
from app.schemas.institution import InstitutionExportQuery
from app.schemas.user import AdminExportQuery, UserExportQuery
from app.services import export_service
from app.services.access_service import ensure_institution_access, ensure_user_active
from app.services.import_service import REPORT_COLUMNS, ImportMode, ImportService, report_rows
from app.services.institution_service import InstitutionService
from app.services.job_service import job_file_path, job_input_path
from app.services.permission_service import PermissionService
from app.services.user_service import UserService

logger = logging.getLogger("app.worker")

STALE_JOB_AFTER = timedelta(hours=2)


@dataclass
class WorkerContext:
    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    redis: Redis
    email_sender: EmailSender
    last_purge: Any = field(default=None)


async def run_once(ctx: WorkerContext) -> bool:
    """Do one round of work. Returns True if anything was processed."""
    published = await relay_outbox(
        ctx.sessionmaker, RedisStreamPublisher(ctx.redis, ctx.settings), batch_size=ctx.settings.OUTBOX_BATCH_SIZE
    )
    job_done = await process_next_job(ctx)
    now = utcnow()
    if ctx.last_purge is None or now - ctx.last_purge >= timedelta(minutes=ctx.settings.WORKER_PURGE_INTERVAL_MINUTES):
        await housekeeping(ctx)
        ctx.last_purge = now
    return bool(published) or job_done


async def run_forever(ctx: WorkerContext, stop: asyncio.Event) -> None:
    logger.info("worker started", extra={"extra_fields": {"pid": os.getpid()}})
    while not stop.is_set():
        try:
            busy = await run_once(ctx)
        except Exception:
            logger.exception("worker iteration failed")
            busy = False
        if not busy:
            try:
                await asyncio.wait_for(stop.wait(), timeout=ctx.settings.WORKER_POLL_SECONDS)
            except TimeoutError:
                pass
    logger.info("worker stopped")


# ---------------------------------------------------------------------- jobs


async def claim_job(ctx: WorkerContext) -> BackgroundJob | None:
    async with ctx.sessionmaker() as db:
        job = (
            await db.execute(
                select(BackgroundJob)
                .where(BackgroundJob.status == JobStatus.QUEUED)
                .order_by(BackgroundJob.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if job is None:
            return None
        job.status = JobStatus.RUNNING
        job.started_at = utcnow()
        job.attempts += 1
        job.error_message = None
        await db.commit()
        return job


async def process_next_job(ctx: WorkerContext) -> bool:
    job = await claim_job(ctx)
    if job is None:
        return False
    if job.job_type == JobType.USER_IMPORT:
        await _process_import(ctx, job)
        return True
    try:
        row_count, user = await _run_export(ctx, job)
    except Exception as exc:
        logger.exception("job failed", extra={"extra_fields": {"job_id": job.public_id}})
        retry = job.attempts < ctx.settings.JOB_MAX_ATTEMPTS and not isinstance(exc, PermissionError)
        await _finish(
            ctx,
            job,
            status=JobStatus.QUEUED if retry else JobStatus.FAILED,
            error=str(exc)[:500] or exc.__class__.__name__,
        )
        return True

    expires_at = utcnow() + timedelta(hours=ctx.settings.EXPORT_FILE_TTL_HOURS)
    path = job_file_path(ctx.settings, job)
    await _finish(
        ctx,
        job,
        status=JobStatus.COMPLETED,
        row_count=row_count,
        file_size_bytes=path.stat().st_size,
        expires_at=expires_at,
    )
    notifier = Notifier(None, ctx.email_sender, ctx.settings)
    notifier.export_ready(
        user, job_id=job.public_id, row_count=row_count, expires_hours=ctx.settings.EXPORT_FILE_TTL_HOURS
    )
    await notifier.flush()
    return True


async def _process_import(ctx: WorkerContext, job: BackgroundJob) -> None:
    """Imports never retry automatically: a second run could repeat writes. The owner sees why it failed."""
    settings = ctx.settings
    input_path = job_input_path(settings, job)
    request_ctx = RequestContext(ip_address=None, user_agent="worker", request_id=f"job-{job.public_id}")
    notifier = Notifier(None, ctx.email_sender, settings)
    try:
        async with ctx.sessionmaker() as db:
            actor = await _authorised_actor(db, job)
            users = UserService(db, settings, request_ctx, notifier)
            result = await ImportService(users).import_users(
                actor,
                input_path.read_bytes(),
                dry_run=bool(job.parameters.get("dry_run")),
                mode=ImportMode(job.parameters.get("mode", ImportMode.ALL_OR_NOTHING)),
                max_rows=settings.IMPORT_JOB_MAX_ROWS,
                max_bytes=settings.IMPORT_JOB_MAX_FILE_BYTES,
            )
            db.expunge(actor)
    except AppError as exc:
        await _finish(ctx, job, status=JobStatus.FAILED, error=exc.message[:500])
        input_path.unlink(missing_ok=True)
        return
    except Exception as exc:
        logger.exception("import job failed", extra={"extra_fields": {"job_id": job.public_id}})
        await _finish(ctx, job, status=JobStatus.FAILED, error=str(exc)[:500] or exc.__class__.__name__)
        input_path.unlink(missing_ok=True)
        return

    path = job_file_path(settings, job)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(report_rows(result))
    input_path.unlink(missing_ok=True)
    job.file_name = f"user-import-report-{job.public_id}.csv"
    summary = {key: result[key] for key in ("dry_run", "mode", "total_rows", "valid_rows", "invalid_rows", "created")}
    await _finish(
        ctx,
        job,
        status=JobStatus.COMPLETED,
        row_count=result["total_rows"],
        file_size_bytes=path.stat().st_size,
        expires_at=utcnow() + timedelta(hours=settings.EXPORT_FILE_TTL_HOURS),
        result=summary,
    )
    await notifier.flush()  # account set-up emails for the imported users
    notifier.import_finished(
        actor,
        job_id=job.public_id,
        summary=f"{result['created']} created, {result['invalid_rows']} with problems",
        expires_hours=settings.EXPORT_FILE_TTL_HOURS,
    )
    await notifier.flush()


async def _authorised_actor(db: AsyncSession, job: BackgroundJob) -> User:
    actor = await db.get(User, job.requested_by_id)
    if actor is None:
        raise PermissionError("The requesting user no longer exists")
    try:  # permissions are re-checked at run time: access may have changed since queuing
        ensure_user_active(actor)
        await ensure_institution_access(actor, InstitutionRepository(db))
    except Exception as exc:
        raise PermissionError("The requesting user no longer has access") from exc
    actor.grant(await PermissionService(db).effective_for(actor))
    return actor


async def _run_export(ctx: WorkerContext, job: BackgroundJob) -> tuple[int, User]:
    settings = ctx.settings
    request_ctx = RequestContext(ip_address=None, user_agent="worker", request_id=f"job-{job.public_id}")
    filters = job.parameters.get("filters", {})

    # A constrained TypeVar (see export_service.ExportModel) lets stream_csv() check `.id` against whichever
    # concrete model it's called with — but that means a call site can't pre-select the model into a
    # `type[Institution] | type[User]`-typed variable across branches and pass that Union in; picking the
    # column/loader tuple to go with it is exactly that dynamic dispatch, so it's `Any` here on purpose.
    model: Any

    async with ctx.sessionmaker() as db:
        actor = await _authorised_actor(db, job)

        if job.job_type == JobType.INSTITUTION_EXPORT:
            service = InstitutionService(db, settings, request_ctx)
            conditions = await service.filter_conditions(
                actor, InstitutionExportQuery.model_validate(filters), action="export"
            )
            model, columns = export_service.Institution, export_service.INSTITUTION_EXPORT_COLUMNS
            options, loader = export_service.INSTITUTION_EXPORT_OPTIONS, export_service.INSTITUTION_COUNTS_LOADER
            resource = "institutions"
        elif job.job_type == JobType.EMPLOYER_EXPORT:
            service = InstitutionService(db, settings, request_ctx, org_type=OrganizationType.EMPLOYER)
            conditions = await service.filter_conditions(
                actor, EmployerExportQuery.model_validate(filters), action="export"
            )
            model, columns = export_service.Institution, export_service.EMPLOYER_EXPORT_COLUMNS
            options, loader = export_service.INSTITUTION_EXPORT_OPTIONS, export_service.INSTITUTION_COUNTS_LOADER
            resource = "employers"
        else:
            users = UserService(db, settings, request_ctx, Notifier(None, ctx.email_sender, settings))
            if job.job_type == JobType.ADMIN_EXPORT:
                user_filters = AdminExportQuery.model_validate(filters).as_user_filters(UserExportQuery)
                conditions = await users.filter_conditions(
                    actor, user_filters, only_role=Role.ADMIN, action=Action.EXPORT
                )
                resource = "admins"
            else:
                conditions = await users.filter_conditions(
                    actor, UserExportQuery.model_validate(filters), action=Action.EXPORT
                )
                resource = "users"
            model, columns = export_service.User, export_service.USER_EXPORT_COLUMNS
            options, loader = export_service.USER_EXPORT_OPTIONS, None
        db.expunge(actor)

    path = job_file_path(settings, job)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".part")
    counter = [0]

    def count(rows: int) -> None:
        counter[0] += rows

    with temporary.open("wb") as handle:
        async for chunk in export_service.stream_csv(
            ctx.sessionmaker,
            model,
            conditions,
            columns,
            options=options,
            max_rows=settings.EXPORT_MAX_ROWS,
            batch_size=settings.EXPORT_BATCH_SIZE,
            extra_loader=loader,
            on_rows=count,
        ):
            handle.write(chunk)
    temporary.replace(path)
    job.file_name = export_service.export_filename(resource)
    return counter[0], actor


async def _finish(ctx: WorkerContext, job: BackgroundJob, *, status: JobStatus, **values: Any) -> None:
    async with ctx.sessionmaker() as db:
        await db.execute(
            update(BackgroundJob)
            .where(BackgroundJob.id == job.id)
            .values(
                status=status,
                finished_at=utcnow() if status != JobStatus.QUEUED else None,
                error_message=values.pop("error", None),
                file_name=job.file_name,
                **values,
            )
        )
        await db.commit()


# ---------------------------------------------------------------------- housekeeping


async def housekeeping(ctx: WorkerContext) -> None:
    now = utcnow()
    async with ctx.sessionmaker() as db:
        # Jobs whose worker crashed go back to the queue.
        await db.execute(
            update(BackgroundJob)
            .where(BackgroundJob.status == JobStatus.RUNNING, BackgroundJob.started_at < now - STALE_JOB_AFTER)
            .values(status=JobStatus.QUEUED)
        )
        expired = list(
            (
                await db.execute(
                    select(BackgroundJob).where(
                        BackgroundJob.status == JobStatus.COMPLETED, BackgroundJob.expires_at <= now
                    )
                )
            ).scalars()
        )
        for job in expired:
            job_file_path(ctx.settings, job).unlink(missing_ok=True)
            job_input_path(ctx.settings, job).unlink(missing_ok=True)
            job.status = JobStatus.EXPIRED
        await db.commit()
    await purge_expired(ctx.settings, sessionmaker=ctx.sessionmaker)
