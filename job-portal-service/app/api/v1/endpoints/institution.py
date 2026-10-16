"""An institution's view of its own students' job applications and placements, and its placement drives."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder
from sqlalchemy import func, select

from app.api.deps import (
    CurrentAuth,
    DbSession,
    DriveIdParam,
    RequireEmployer,
    RequireEmployerAdmin,
    RequireInstitutionHead,
    RequireInstitutionMember,
    SettingsDep,
    WriteRateLimit,
)
from app.api.presenters import company_names
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import PermissionDeniedError
from app.core.ids import parse_public_id
from app.core.security import AccessTokenClaims
from app.domain.enums import ApplicationStatus, DriveStatus
from app.models.application import Application
from app.models.offer import Offer, PlacementDrive
from app.permissions.policy import (
    can_manage_careers,
    is_employer_admin,
    is_employer_member,
    is_institution_head,
    is_institution_staff,
)
from app.schemas.application import (
    CandidateSummary,
    InstitutionApplicationOut,
    InstitutionApplicationPage,
    InstitutionSummaryResponse,
)
from app.schemas.drive import AttachJob, DriveCreate, DriveOut, DrivePage, DriveRespond, DriveResponse
from app.services.application_service import ApplicationService
from app.services.drive_service import DriveService
from app.services.job_service import JobService

router = APIRouter(prefix="/institution", tags=["Institution (placements)"])
drives = APIRouter(prefix="/drives", tags=["Placement drives"])


# ---------------------------------------------------------------- applications and placements of my students
async def _rows(db: DbSession, settings: SettingsDep, org: int, *, status: str | None, drive_id: int | None, page: int, per_page: int) -> tuple[list[InstitutionApplicationOut], int]:
    service = ApplicationService(db, settings)
    rows, total = await service.list_for_institution(org, status=status, drive_id=drive_id, page=page, per_page=per_page)
    names = await company_names(db, {job.employer_org_id for _, job, _ in rows})
    offers = {o.application_id: o for o in (await db.execute(select(Offer).where(Offer.application_id.in_([a.id for a, _, _ in rows])))).scalars()} if rows else {}
    out = []
    for application, job, user in rows:
        offer = offers.get(application.id)
        name = " ".join(x for x in ((user.first_name if user else ""), (user.last_name if user else "")) if x) or "Student"
        out.append(
            InstitutionApplicationOut(
                application_id=application.public_id, student=CandidateSummary(user_id=application.user_id, name=name, email=user.email if user else None), job_id=job.public_id, job_title=job.title,
                company_name=names.get(job.employer_org_id), drive_id=job.drive_id, status=application.status, applied_at=application.created_at, status_changed_at=application.status_changed_at,
                ctc=offer.ctc if offer and application.status == ApplicationStatus.PLACED else None, currency=offer.currency if offer and application.status == ApplicationStatus.PLACED else None,
            )
        )
    return out, total


@router.get(
    "/applications", response_model=InstitutionApplicationPage, summary="My institution's students' applications",
    description="Staff and the head of an institution see how far their students have got: the job, the company and the status. Not the employer's screening or notes.", responses=errors(*AUTHENTICATED),
)
async def applications(
    auth: RequireInstitutionMember, db: DbSession, settings: SettingsDep, status: Annotated[ApplicationStatus | None, Query()] = None, drive_id: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> InstitutionApplicationPage:
    out, total = await _rows(db, settings, auth.organization_id or 0, status=status.value if status else None, drive_id=parse_public_id(drive_id) if drive_id else None, page=page, per_page=per_page)
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="status_changed_at", sort_order=SortOrder.DESC)
    return InstitutionApplicationPage(message="", applications=out, page_context=context)


@router.get("/placements", response_model=InstitutionApplicationPage, summary="My institution's placed students", responses=errors(*AUTHENTICATED))
async def placements(
    auth: RequireInstitutionMember, db: DbSession, settings: SettingsDep, page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20
) -> InstitutionApplicationPage:
    out, total = await _rows(db, settings, auth.organization_id or 0, status=ApplicationStatus.PLACED.value, drive_id=None, page=page, per_page=per_page)
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="status_changed_at", sort_order=SortOrder.DESC)
    return InstitutionApplicationPage(message="", applications=out, page_context=context)


@router.get("/summary", response_model=InstitutionSummaryResponse, summary="Placement numbers for my institution", responses=errors(*AUTHENTICATED))
async def summary(auth: RequireInstitutionMember, db: DbSession) -> InstitutionSummaryResponse:
    org = auth.organization_id or 0
    by_status = {s: int(n) for s, n in (await db.execute(select(Application.status, func.count()).where(Application.organization_id == org).group_by(Application.status))).all()}
    students = int((await db.execute(select(func.count(func.distinct(Application.user_id))).where(Application.organization_id == org))).scalar_one())
    placed_students = int((await db.execute(select(func.count(func.distinct(Application.user_id))).where(Application.organization_id == org, Application.status == ApplicationStatus.PLACED))).scalar_one())
    employers = int((await db.execute(select(func.count(func.distinct(Application.employer_org_id))).where(Application.organization_id == org))).scalar_one())
    return InstitutionSummaryResponse(
        message="", students_applied=students, applications=sum(by_status.values()), by_status=by_status, placed=by_status.get(ApplicationStatus.PLACED.value, 0), placed_students=placed_students, employers=employers
    )


# ---------------------------------------------------------------- placement drives
async def _drive_out(db: DbSession, drive: PlacementDrive) -> DriveOut:
    names = await company_names(db, {drive.employer_org_id, drive.organization_id})
    out = DriveOut.model_validate(drive)
    return out.model_copy(update={"company_name": names.get(drive.employer_org_id), "institution_name": names.get(drive.organization_id)})


@drives.post(
    "", response_model=DriveResponse, status_code=201, summary="Invite a company to a placement drive (institution head)",
    description="The company must be verified. Once it accepts, its jobs can be attached; they are then visible only to this institution's students, its staff and its head.",
    responses=errors(*AUTHENTICATED, 422), dependencies=[WriteRateLimit],
)
async def propose(body: DriveCreate, auth: RequireInstitutionHead, db: DbSession, settings: SettingsDep) -> DriveResponse:
    drive = await DriveService(db, settings).propose(auth, body.employer_id, title=body.title, description=body.description, drive_date=body.drive_date)
    return DriveResponse(message="Invitation sent.", drive=await _drive_out(db, drive))


@drives.get("", response_model=DrivePage, summary="Placement drives I am part of", responses=errors(*AUTHENTICATED))
async def list_drives(
    auth: CurrentAuth, db: DbSession, settings: SettingsDep, status: Annotated[DriveStatus | None, Query()] = None, page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DrivePage:
    if not (is_institution_staff(auth) or is_institution_head(auth) or is_employer_member(auth) or is_employer_admin(auth) or can_manage_careers(auth)):
        raise PermissionDeniedError()
    rows, total = await DriveService(db, settings).list_for(auth, status=status.value if status else None, page=page, per_page=per_page)
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC)
    return DrivePage(message="", drives=[await _drive_out(db, d) for d in rows], page_context=context)


@drives.get("/{drive_id}", response_model=DriveResponse, summary="A drive with its numbers", responses=errors(*AUTHENTICATED, 404))
async def get_drive(drive_id: DriveIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> DriveResponse:
    service = DriveService(db, settings)
    drive = await service.get_visible(auth, drive_id)
    return DriveResponse(message="", drive=await _drive_out(db, drive), summary=await service.summary(drive))


@drives.post("/{drive_id}/respond", response_model=DriveResponse, summary="Accept or decline an invitation (employer admin)", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit])
async def respond(drive_id: DriveIdParam, body: DriveRespond, auth: RequireEmployerAdmin, db: DbSession, settings: SettingsDep) -> DriveResponse:
    service = DriveService(db, settings)
    drive = await service.get_visible(auth, drive_id)
    if drive.employer_org_id != auth.organization_id:
        raise PermissionDeniedError()
    return DriveResponse(message="Accepted." if body.accept else "Declined.", drive=await _drive_out(db, await service.respond(auth, drive, accept=body.accept)))


@drives.post(
    "/{drive_id}/jobs", response_model=DriveResponse, summary="Attach one of my company's jobs to an accepted drive (recruiter)",
    description="The job becomes restricted to the drive's institution (it is re-matched if open).", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit],
)
async def attach(drive_id: DriveIdParam, body: AttachJob, auth: RequireEmployer, db: DbSession, settings: SettingsDep) -> DriveResponse:
    service = DriveService(db, settings)
    drive = await service.get_visible(auth, drive_id)
    job = await JobService(db, settings).get_for_employer(auth, body.job_id)
    await service.attach_job(drive, job)
    return DriveResponse(message="Job attached.", drive=await _drive_out(db, drive), summary=await service.summary(drive))


async def _finish(drive_id: int, auth: AccessTokenClaims, db: DbSession, settings: SettingsDep, *, complete: bool) -> DriveResponse:
    service = DriveService(db, settings)
    drive = await service.get_visible(auth, drive_id)
    if not (is_institution_head(auth) and drive.organization_id == auth.organization_id) and not (is_employer_admin(auth) and drive.employer_org_id == auth.organization_id) and not can_manage_careers(auth):
        raise PermissionDeniedError()
    drive = await service.finish(drive, complete=complete)
    return DriveResponse(message="Completed." if complete else "Cancelled.", drive=await _drive_out(db, drive), summary=await service.summary(drive))


@drives.post("/{drive_id}/complete", response_model=DriveResponse, summary="Mark a drive completed (its head, its employer's admin)", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit])
async def complete(drive_id: DriveIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> DriveResponse:
    return await _finish(drive_id, auth, db, settings, complete=True)


@drives.post(
    "/{drive_id}/cancel", response_model=DriveResponse, summary="Cancel a drive", description="Its open and draft jobs close: they were only ever for this institution.",
    responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit],
)
async def cancel(drive_id: DriveIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> DriveResponse:
    return await _finish(drive_id, auth, db, settings, complete=False)

