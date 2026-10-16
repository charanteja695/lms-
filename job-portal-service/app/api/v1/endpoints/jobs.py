"""A company's jobs and the platform's job approval queue.

The super admin (careers manager) runs hiring: they post a job for any company (`employer_org_id`), and a job they
submit opens at once (no approval step for their own posting). A company's own team, where one exists, works on its own jobs.
"""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    DbSession,
    JobIdParam,
    RequireCareersManager,
    RequireEmployerOrManager,
    SettingsDep,
    WriteRateLimit,
)
from app.api.presenters import company_names, employer_job_out
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.security import AccessTokenClaims
from app.domain.enums import JobStatus
from app.models.job import Job
from app.models.refs import OrgRef
from app.permissions.policy import can_manage_careers, is_employer_member
from app.schemas.job import EmployerJobPage, EmployerJobResponse, JobCreate, JobUpdate, ReasonRequest, ReviewJobRequest
from app.services.job_service import JobService

router = APIRouter(prefix="/employer/jobs", tags=["Jobs (employer)"])
admin = APIRouter(prefix="/admin/jobs", tags=["Job approval"])


async def _present(service: JobService, db: DbSession, job: Job, *, message: str = "") -> EmployerJobResponse:
    names = await company_names(db, {job.employer_org_id})
    stats = await service.stats([job])
    applications, placed = stats.get(job.id, (0, 0))
    return EmployerJobResponse(
        message=message, job=employer_job_out(job, names.get(job.employer_org_id), institution_ids=await service.institution_ids(job), applications=applications, placed=placed)
    )


def _employer(auth: AccessTokenClaims, requested: int | None) -> int:
    """The company a request acts for: a company member's own; a careers manager names it."""
    if is_employer_member(auth):
        return auth.organization_id or 0
    if requested is None:
        raise ValidationFailedError(details=[{"field": "employer_org_id", "code": "REQUIRED", "message": "Choose the company this job is for"}])
    return requested


@router.post(
    "", response_model=EmployerJobResponse, status_code=201, summary="Draft a job",
    description="Title, description, skills (required / preferred), experience, location or remote, pay range, eligibility (graduation years, certificates, minimum scores, "
    "institutions), openings, deadline, and the hiring pipeline template. Submit it for approval when it is ready.", responses=errors(*AUTHENTICATED), dependencies=[WriteRateLimit],
)
async def create_job(body: JobCreate, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> EmployerJobResponse:
    service = JobService(db, settings)
    employer_org_id = _employer(auth, body.employer_org_id)
    company = None if is_employer_member(auth) else await db.get(OrgRef, employer_org_id)
    if not is_employer_member(auth) and (company is None or company.org_type != "employer"):
        raise NotFoundError("Company not found.", code="EMPLOYER_NOT_FOUND")
    job = await service.create(auth, employer_org_id, body.model_dump(exclude={"employer_org_id"}))
    return await _present(service, db, job, message="Draft saved.")


@router.get(
    "", response_model=EmployerJobPage, summary="Jobs I manage",
    description="A company member: their company's jobs. A careers manager: every company's, or one company's with `employer_org_id`.", responses=errors(*AUTHENTICATED),
)
async def list_jobs(
    auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep, status: Annotated[JobStatus | None, Query()] = None, q: Annotated[str | None, Query(max_length=100)] = None,
    employer_org_id: Annotated[int | None, Query(ge=1)] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EmployerJobPage:
    service = JobService(db, settings)
    company = (auth.organization_id or 0) if is_employer_member(auth) else employer_org_id
    jobs, total = await service.list_for_employer(company, status=status.value if status else None, q=q, page=page, per_page=per_page)
    names = await company_names(db, {j.employer_org_id for j in jobs})
    stats = await service.stats(jobs)
    out = [employer_job_out(j, names.get(j.employer_org_id), institution_ids=await service.institution_ids(j), applications=stats[j.id][0], placed=stats[j.id][1]) for j in jobs]
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC)
    return EmployerJobPage(message="", jobs=out, page_context=context)


@router.get("/{job_id}", response_model=EmployerJobResponse, summary="One of my company's jobs", responses=errors(*AUTHENTICATED, 404))
async def get_job(job_id: JobIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> EmployerJobResponse:
    service = JobService(db, settings)
    return await _present(service, db, await service.get_for_employer(auth, job_id))


@router.patch(
    "/{job_id}", response_model=EmployerJobResponse, summary="Edit a job",
    description="A draft, paused or open job can be edited (an open job is re-matched when a matching field changes). Not while pending approval (`409 JOB_PENDING`); "
    "the pipeline is locked once people have applied (`409 PIPELINE_LOCKED`).", responses=errors(*AUTHENTICATED, 404, 409, 422), dependencies=[WriteRateLimit],
)
async def update_job(job_id: JobIdParam, body: JobUpdate, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> EmployerJobResponse:
    service = JobService(db, settings)
    job = await service.update(await service.get_for_employer(auth, job_id), body.model_dump(exclude_unset=True))
    return await _present(service, db, job, message="Saved.")


@router.post(
    "/{job_id}/submit", response_model=EmployerJobResponse, summary="Submit for approval (a careers manager's job opens at once)",
    description="Needs a verified company (`409 EMPLOYER_NOT_VERIFIED`) and a complete job: a required skill, a description, a future deadline, real courses and institutions.",
    responses=errors(*AUTHENTICATED, 404, 409, 422), dependencies=[WriteRateLimit],
)
async def submit_job(job_id: JobIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> EmployerJobResponse:
    service = JobService(db, settings)
    job = await service.submit(await service.get_for_employer(auth, job_id))
    if can_manage_careers(auth):  # the super admin's own posting needs no approval: it opens now
        job = await service.review(job, auth.user_id, approve=True, note=None)
        return await _present(service, db, job, message="Published: the job is open.")
    return await _present(service, db, job, message="Submitted for approval.")


@router.post("/{job_id}/withdraw-submission", response_model=EmployerJobResponse, summary="Take a job back from approval", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit])
async def withdraw_submission(job_id: JobIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> EmployerJobResponse:
    service = JobService(db, settings)
    return await _present(service, db, await service.withdraw_submission(await service.get_for_employer(auth, job_id)), message="Back to draft.")


@router.post("/{job_id}/pause", response_model=EmployerJobResponse, summary="Pause an open job (no new applications)", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit])
async def pause_job(job_id: JobIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> EmployerJobResponse:
    service = JobService(db, settings)
    return await _present(service, db, await service.pause(await service.get_for_employer(auth, job_id)), message="Paused.")


@router.post("/{job_id}/resume", response_model=EmployerJobResponse, summary="Reopen a paused job", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit])
async def resume_job(job_id: JobIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> EmployerJobResponse:
    service = JobService(db, settings)
    return await _present(service, db, await service.resume(await service.get_for_employer(auth, job_id)), message="Open again.")


@router.post(
    "/{job_id}/close", response_model=EmployerJobResponse, summary="Close a job",
    description="No new applications; people already in the pipeline stay in it. A job also closes itself at its deadline and when its openings are filled.",
    responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit],
)
async def close_job(job_id: JobIdParam, body: ReasonRequest, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> EmployerJobResponse:
    service = JobService(db, settings)
    return await _present(service, db, await service.close(await service.get_for_employer(auth, job_id), body.reason), message="Closed.")


# ---------------------------------------------------------------- the platform's approval queue
@admin.get("", response_model=EmployerJobPage, summary="Jobs waiting for approval (careers manager)", description="Oldest submission first.", responses=errors(*AUTHENTICATED))
async def approval_queue(
    _: RequireCareersManager, db: DbSession, settings: SettingsDep, status: Annotated[JobStatus, Query()] = JobStatus.PENDING_APPROVAL,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EmployerJobPage:
    service = JobService(db, settings)
    jobs, total = await service.list_for_review(status.value, page=page, per_page=per_page)
    names = await company_names(db, {j.employer_org_id for j in jobs})
    stats = await service.stats(jobs)
    out = [employer_job_out(j, names.get(j.employer_org_id), institution_ids=await service.institution_ids(j), applications=stats[j.id][0], placed=stats[j.id][1]) for j in jobs]
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="submitted_at", sort_order=SortOrder.ASC)
    return EmployerJobPage(message="", jobs=out, page_context=context)


@admin.post(
    "/{job_id}/review", response_model=EmployerJobResponse, summary="Approve or reject a job",
    description="Approving opens the job: students are matched to it and `job.published` is emitted. A rejection returns it to draft with the `note`.", responses=errors(*AUTHENTICATED, 404, 409, 422),
)
async def review_job(job_id: JobIdParam, body: ReviewJobRequest, auth: RequireCareersManager, db: DbSession, settings: SettingsDep) -> EmployerJobResponse:
    service = JobService(db, settings)
    job = await service.review(await service.get(job_id), auth.user_id, approve=body.approve, note=body.note)
    return await _present(service, db, job, message="Approved." if body.approve else "Sent back to the employer.")

