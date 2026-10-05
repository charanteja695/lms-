"""Company profiles: an employer's own, the public view of a verified company, and the platform's verification queue."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    CurrentAuth,
    DbSession,
    OrgIdParam,
    RequireCareersManager,
    RequireEmployer,
    RequireEmployerAdmin,
    WriteRateLimit,
)
from app.api.presenters import company_names, employer_out
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import NotFoundError
from app.domain.enums import EmployerStatus
from app.permissions.policy import can_manage_careers
from app.schemas.employer import EmployerPage, EmployerProfileUpdate, EmployerResponse, NoteRequest, ReviewRequest
from app.services.employer_service import EmployerService

router = APIRouter(tags=["Employers"])
admin = APIRouter(prefix="/admin/employers", tags=["Employer verification"])


async def _own(db: DbSession, auth: RequireEmployer) -> EmployerResponse:
    service = EmployerService(db)
    profile = await service.get_or_create(auth.organization_id or 0)
    await db.commit()
    return EmployerResponse(
        message="", employer=employer_out(profile, await service.company_name(profile.organization_id), open_jobs=await service.open_job_count(profile.organization_id))
    )


@router.get(
    "/employer/profile", response_model=EmployerResponse, summary="My company's profile and its verification status",
    description="A company's jobs go live only while `status` is `verified`. The first call creates an empty `draft`.", responses=errors(*AUTHENTICATED),
)
async def my_profile(auth: RequireEmployer, db: DbSession) -> EmployerResponse:
    return await _own(db, auth)


@router.patch(
    "/employer/profile", response_model=EmployerResponse, summary="Edit the company profile (employer admin)",
    description="Editing after a rejection starts a new submission. The company name comes from user-management.", responses=errors(*AUTHENTICATED, 409), dependencies=[WriteRateLimit],
)
async def update_profile(body: EmployerProfileUpdate, auth: RequireEmployerAdmin, db: DbSession) -> EmployerResponse:
    service = EmployerService(db)
    org = auth.organization_id or 0
    profile = await service.update(org, body.model_dump(exclude_unset=True))
    return EmployerResponse(message="Saved.", employer=employer_out(profile, await service.company_name(org), open_jobs=await service.open_job_count(org)))


@router.post(
    "/employer/profile/submit", response_model=EmployerResponse, summary="Submit the company profile for verification (employer admin)",
    description="Needs `about`, `website` and `industry`. A platform careers manager verifies or rejects it.", responses=errors(*AUTHENTICATED, 409, 422), dependencies=[WriteRateLimit],
)
async def submit(auth: RequireEmployerAdmin, db: DbSession) -> EmployerResponse:
    service = EmployerService(db)
    org = auth.organization_id or 0
    profile = await service.submit(org)
    return EmployerResponse(message="Submitted for verification.", employer=employer_out(profile, await service.company_name(org)))


@router.get(
    "/companies/{organization_id}", response_model=EmployerResponse, summary="A company's public profile",
    description="Verified companies only (a company's own team and careers managers also see theirs while it is being reviewed).", responses=errors(*AUTHENTICATED, 404),
)
async def get_employer(organization_id: OrgIdParam, auth: CurrentAuth, db: DbSession) -> EmployerResponse:
    service = EmployerService(db)
    profile = await service.get(organization_id)
    mine = auth.organization_id == organization_id
    if profile is None or (profile.status != EmployerStatus.VERIFIED and not mine and not can_manage_careers(auth)):
        raise NotFoundError("Employer not found.", code="EMPLOYER_NOT_FOUND")
    return EmployerResponse(
        message="", employer=employer_out(profile, await service.company_name(organization_id), open_jobs=await service.open_job_count(organization_id), include_review=mine or can_manage_careers(auth))
    )


@admin.get("", response_model=EmployerPage, summary="Company profiles for review (careers manager)", description="Oldest submission first.", responses=errors(*AUTHENTICATED))
async def review_queue(
    _: RequireCareersManager, db: DbSession, status: Annotated[EmployerStatus | None, Query()] = EmployerStatus.PENDING,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EmployerPage:
    profiles, total = await EmployerService(db).list_for_review(status.value if status else None, page=page, per_page=per_page)
    names = await company_names(db, {p.organization_id for p in profiles})
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="submitted_at", sort_order=SortOrder.ASC)
    return EmployerPage(message="", employers=[employer_out(p, names.get(p.organization_id, "Company")) for p in profiles], page_context=context)


@admin.post(
    "/{organization_id}/review", response_model=EmployerResponse, summary="Verify or reject a company", description="A rejection needs a `note`: it is what the employer reads.",
    responses=errors(*AUTHENTICATED, 404, 409, 422),
)
async def review(organization_id: OrgIdParam, body: ReviewRequest, auth: RequireCareersManager, db: DbSession) -> EmployerResponse:
    service = EmployerService(db)
    profile = await service.review(organization_id, auth.user_id, approve=body.approve, note=body.note)
    return EmployerResponse(message="Verified." if body.approve else "Rejected.", employer=employer_out(profile, await service.company_name(organization_id)))


@admin.post(
    "/{organization_id}/suspend", response_model=EmployerResponse, summary="Suspend a verified company",
    description="Every job it has open is paused. Only an admin's suspension is lifted by `reinstate`; a suspended user-management account lifts itself when the account is reactivated.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def suspend(organization_id: OrgIdParam, body: NoteRequest, auth: RequireCareersManager, db: DbSession) -> EmployerResponse:
    service = EmployerService(db)
    profile, _ = await service.suspend(organization_id, source="admin", by_user_id=auth.user_id, note=body.note)
    return EmployerResponse(message="Suspended.", employer=employer_out(profile, await service.company_name(organization_id)))


@admin.post("/{organization_id}/reinstate", response_model=EmployerResponse, summary="Lift a suspension", description="Paused jobs stay paused: the employer resumes them.", responses=errors(*AUTHENTICATED, 404, 409))
async def reinstate(organization_id: OrgIdParam, _: RequireCareersManager, db: DbSession) -> EmployerResponse:
    service = EmployerService(db)
    profile = await service.reinstate(organization_id, source="admin")
    return EmployerResponse(message="Reinstated.", employer=employer_out(profile, await service.company_name(organization_id)))
