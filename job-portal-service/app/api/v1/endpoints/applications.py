"""A student's applications: apply with a resume, follow the pipeline, withdraw, answer an offer."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    ApplicationIdParam,
    ApplyRateLimit,
    CareerDep,
    DbSession,
    JobIdParam,
    RequireStudent,
    SettingsDep,
    WriteRateLimit,
)
from app.api.presenters import company_names, my_application_out
from app.api.responses import AUTHENTICATED, errors
from app.domain.enums import ApplicationStatus
from app.models.application import Application
from app.models.job import Job
from app.schemas.application import (
    ApplyRequest,
    MyApplicationPage,
    MyApplicationResponse,
    OfferOut,
    OfferResponse,
    OfferResponseRequest,
    WithdrawRequest,
)
from app.services.application_service import ApplicationService
from app.services.offer_service import OfferService

router = APIRouter(tags=["Applications (student)"])


async def _mine(service: ApplicationService, application: Application, job: Job, db: DbSession, *, message: str = "") -> MyApplicationResponse:
    names = await company_names(db, {job.employer_org_id})
    offer = await OfferService(db, service.settings).for_application(application)
    return MyApplicationResponse(message=message, application=my_application_out(application, job, names.get(job.employer_org_id), history=await service.history(application), offer=offer))


@router.post(
    "/job-board/{job_id}/apply", response_model=MyApplicationResponse, status_code=201, summary="Apply to a job with one of my resumes",
    description="Needs a verified skill profile (`409 PROFILE_NOT_VERIFIED`), the job's eligibility rules (`403 NOT_ELIGIBLE`, with the reasons), and an open job before its deadline. "
    "The resume is frozen at this moment: later edits never change what the recruiter sees. One application per job (`409 ALREADY_APPLIED`).",
    responses=errors(*AUTHENTICATED, 404, 409), dependencies=[ApplyRateLimit],
)
async def apply(job_id: JobIdParam, body: ApplyRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep, career: CareerDep) -> MyApplicationResponse:
    service = ApplicationService(db, settings)
    application = await service.apply(auth, job_id, resume_id=body.resume_id, cover_note=body.cover_note, career=career)
    return await _mine(service, application, await service.job_of(application), db, message="Application sent.")


@router.get("/applications", response_model=MyApplicationPage, summary="My applications", responses=errors(*AUTHENTICATED))
async def my_applications(
    auth: RequireStudent, db: DbSession, settings: SettingsDep, status: Annotated[ApplicationStatus | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=50)] = 20,
) -> MyApplicationPage:
    service = ApplicationService(db, settings)
    rows, total = await service.list_mine(auth.user_id, status=status.value if status else None, page=page, per_page=per_page)
    names = await company_names(db, {job.employer_org_id for _, job in rows})
    out = [my_application_out(a, j, names.get(j.employer_org_id)) for a, j in rows]
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC)
    return MyApplicationPage(message="", applications=out, page_context=context)


@router.get("/applications/{application_id}", response_model=MyApplicationResponse, summary="One of my applications, with its history", responses=errors(*AUTHENTICATED, 404))
async def get_application(application_id: ApplicationIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> MyApplicationResponse:
    service = ApplicationService(db, settings)
    application = await service.get_mine(auth.user_id, application_id)
    return await _mine(service, application, await service.job_of(application), db)


@router.post(
    "/applications/{application_id}/withdraw", response_model=MyApplicationResponse, summary="Withdraw an application",
    description="Possible at any stage until it is closed. Withdrawing while an offer is open declines the offer.", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit],
)
async def withdraw(application_id: ApplicationIdParam, body: WithdrawRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> MyApplicationResponse:
    service = ApplicationService(db, settings)
    application = await service.withdraw(auth.user_id, await service.get_mine(auth.user_id, application_id), body.note)
    return await _mine(service, application, await service.job_of(application), db, message="Withdrawn.")


@router.post(
    "/applications/{application_id}/offer/respond", response_model=OfferResponse, summary="Accept or decline an offer",
    description="`409 OFFER_EXPIRED` once the offer's time is up (it is then closed as declined); `409 NO_OPEN_OFFER` when there is nothing to answer.", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit],
)
async def respond(application_id: ApplicationIdParam, body: OfferResponseRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> OfferResponse:
    applications = ApplicationService(db, settings)
    offer = await OfferService(db, settings).respond(auth.user_id, await applications.get_mine(auth.user_id, application_id), accept=body.accept, note=body.note)
    return OfferResponse(message="Offer accepted." if body.accept else "Offer declined.", offer=OfferOut.model_validate(offer))
