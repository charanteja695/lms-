"""The recruiter's side of the pipeline: applicants of a job, the AI's recommendations, shortlisting, confirmed rejection batches, moving people
through the stages, notes, offers and placement. Every route is scoped to the caller's own employer (a careers manager may act on any)."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder
from sqlalchemy import select

from app.api.deps import (
    AiRateLimit,
    ApplicationIdParam,
    DbSession,
    GatewayDep,
    JobIdParam,
    RequireEmployerOrManager,
    SettingsDep,
    WriteRateLimit,
)
from app.api.presenters import recruiter_application_detail, recruiter_application_out
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import ValidationFailedError
from app.domain.enums import ApplicationStatus
from app.models.application import Application
from app.models.job import Job
from app.models.refs import UserRef
from app.pipeline import progress as pipeline_progress
from app.schemas.application import (
    BatchOut,
    BatchResponse,
    BulkResult,
    BulkShortlistRequest,
    DecisionOut,
    DecisionPage,
    FunnelResponse,
    NoteIn,
    NoteResponse,
    OfferOut,
    OfferRequest,
    OfferResponse,
    RankingOut,
    RankingResponse,
    RecruiterApplicationDetail,
    RecruiterApplicationOut,
    RecruiterApplicationPage,
    RecruiterApplicationResponse,
    RejectRequest,
    TransitionRequest,
)
from app.services.application_service import ApplicationService, template_of
from app.services.job_service import JobService
from app.services.offer_service import OfferService
from app.services.screening_service import ScreeningService

router = APIRouter(prefix="/employer", tags=["Hiring pipeline (recruiter)"])


async def _detail(service: ApplicationService, db: DbSession, application: Application, job: Job) -> RecruiterApplicationDetail:
    user = await db.get(UserRef, application.user_id)
    return recruiter_application_detail(
        application, user, job, history=await service.history(application), notes=await service.notes(application), offer=await OfferService(db, service.settings).for_application(application)
    )


async def _job(db: DbSession, settings: SettingsDep, auth: RequireEmployerOrManager, job_id: int) -> Job:
    return await JobService(db, settings).get_for_employer(auth, job_id)


# ---------------------------------------------------------------- a job's applicants
@router.get(
    "/jobs/{job_id}/applications", response_model=RecruiterApplicationPage, summary="Applicants of a job",
    description="Filter by `status` (repeat it for several), `min_score` (screening score) and `q` (candidate name); `sort` is `screen` (best first), `match` or `recent`.", responses=errors(*AUTHENTICATED, 404),
)
async def applicants(
    job_id: JobIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep, status: Annotated[list[ApplicationStatus] | None, Query()] = None,
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None, q: Annotated[str | None, Query(max_length=100)] = None, sort: Annotated[str, Query(pattern="^(screen|match|recent)$")] = "screen",
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RecruiterApplicationPage:
    job = await _job(db, settings, auth, job_id)
    rows, total = await ApplicationService(db, settings).list_for_job(
        job, statuses=[s.value for s in status] if status else None, min_score=min_score, sort=sort, q=q, page=page, per_page=per_page
    )
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column=sort, sort_order=SortOrder.DESC)
    return RecruiterApplicationPage(message="", applications=[recruiter_application_out(a, u, job.public_id) for a, u in rows], page_context=context)


@router.get("/jobs/{job_id}/funnel", response_model=FunnelResponse, summary="Applicants by stage", responses=errors(*AUTHENTICATED, 404))
async def funnel(job_id: JobIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> FunnelResponse:
    job = await _job(db, settings, auth, job_id)
    counts = await ApplicationService(db, settings).status_counts(job)
    stages = [{**g, "count": sum(counts.get(s, 0) for s in g["statuses"])} for g in pipeline_progress.stage_groups(template_of(job))]
    return FunnelResponse(message="", job_id=job.public_id, by_status=counts, stages=stages, total=sum(counts.values()), placed=counts.get(ApplicationStatus.PLACED.value, 0), openings=job.openings)


@router.get(
    "/jobs/{job_id}/screening", response_model=RankingResponse, summary="The AI's ranking of undecided applicants (recommendations only)",
    description="Applicants still `applied` or `ai_screened`, best first, bucketed by `shortlist_at` and `reject_below` (defaults from settings). **Nothing here changes any application**: "
    "shortlisting is `POST …/shortlist`; rejecting is a person's confirmed batch, `POST …/reject`.", responses=errors(*AUTHENTICATED, 404),
)
async def ranking(
    job_id: JobIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep, gateway: GatewayDep, shortlist_at: Annotated[int | None, Query(ge=0, le=100)] = None,
    reject_below: Annotated[int | None, Query(ge=0, le=100)] = None,
) -> RankingResponse:
    job = await _job(db, settings, auth, job_id)
    high, low = shortlist_at if shortlist_at is not None else settings.SCREEN_SHORTLIST_DEFAULT_THRESHOLD, reject_below if reject_below is not None else settings.SCREEN_REJECT_BELOW
    if low > high:
        raise ValidationFailedError(details=[{"field": "reject_below", "code": "INVALID_RANGE", "message": "reject_below cannot exceed shortlist_at"}])
    data = await ScreeningService(db, settings, gateway).ranking(job, shortlist_at=high, reject_below=low)
    users = {u.user_id: u for u in (await db.execute(select(UserRef).where(UserRef.user_id.in_([a.user_id for group in data["buckets"].values() for a in group])))).scalars()} if data["buckets"] else {}

    def out(group: list[Application]) -> list[RecruiterApplicationOut]:
        return [recruiter_application_out(a, users.get(a.user_id), job.public_id) for a in group]

    b = data["buckets"]
    return RankingResponse(message="", ranking=RankingOut(shortlist_at=high, reject_below=low, shortlist=out(b["shortlist"]), review=out(b["review"]), reject=out(b["reject"]), unscreened=out(b["unscreened"])))


@router.get(
    "/jobs/{job_id}/screening/decisions", response_model=DecisionPage, summary="The audit log of AI screening decisions",
    description="Every decision with the model, prompt version, input digest and the anonymised input's output — for audit and bias review.", responses=errors(*AUTHENTICATED, 404), dependencies=[AiRateLimit],
)
async def decisions(
    job_id: JobIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep, gateway: GatewayDep, page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 50,
) -> DecisionPage:
    job = await _job(db, settings, auth, job_id)
    rows = await ScreeningService(db, settings, gateway).decisions(job, page=page, per_page=per_page)
    public = {a.id: a.public_id for a in (await db.execute(select(Application).where(Application.id.in_([d.application_id for d in rows])))).scalars()} if rows else {}
    return DecisionPage(
        message="",
        decisions=[
            DecisionOut(
                application_id=public.get(d.application_id), kind=d.kind, source=d.source, model=d.model, prompt_key=d.prompt_key, prompt_version=d.prompt_version, input_digest=d.input_digest,
                score=d.score, recommendation=d.recommendation, output=d.output, created_at=d.created_at,
            )
            for d in rows
        ],
    )


# ---------------------------------------------------------------- decisions: only people
@router.post(
    "/jobs/{job_id}/applications/shortlist", response_model=BulkResult, summary="Shortlist applicants (a recruiter's decision)",
    description="Either `application_ids`, or `threshold` (everyone still undecided whose screening score is at least that).", responses=errors(*AUTHENTICATED, 404, 409, 422), dependencies=[WriteRateLimit],
)
async def shortlist(job_id: JobIdParam, body: BulkShortlistRequest, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> BulkResult:
    if (body.application_ids is None) == (body.threshold is None):
        raise ValidationFailedError(details=[{"field": "application_ids", "code": "EXACTLY_ONE", "message": "Send application_ids or threshold, not both"}])
    job = await _job(db, settings, auth, job_id)
    service = ApplicationService(db, settings)
    moved = await (service.bulk_shortlist(auth, job, list(body.application_ids)) if body.application_ids is not None else service.shortlist_by_threshold(auth, job, body.threshold or 0))
    return BulkResult(message=f"{len(moved)} shortlisted.", count=len(moved), application_ids=[str(a.public_id) for a in moved])


@router.post(
    "/jobs/{job_id}/applications/reject", response_model=BatchResponse, status_code=201, summary="Reject applicants in a confirmed batch",
    description="`confirm` must be true. This is the only way an application is rejected: the AI only recommends, a person confirms each batch. The batch records how many of them "
    "the screening had recommended rejecting and how many it had not.", responses=errors(*AUTHENTICATED, 404, 409, 422), dependencies=[WriteRateLimit],
)
async def reject(job_id: JobIdParam, body: RejectRequest, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> BatchResponse:
    job = await _job(db, settings, auth, job_id)
    batch = await ApplicationService(db, settings).reject_batch(auth, job, list(body.application_ids), reason=body.reason, confirmed=body.confirm, threshold=body.threshold)
    return BatchResponse(message=f"{len(body.application_ids)} rejected.", batch=BatchOut.model_validate(batch))


# ---------------------------------------------------------------- one application
@router.get("/applications/{application_id}", response_model=RecruiterApplicationResponse, summary="One applicant: resume as sent, screening, assessment, history, notes", responses=errors(*AUTHENTICATED, 404))
async def get_application(application_id: ApplicationIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> RecruiterApplicationResponse:
    service = ApplicationService(db, settings)
    application, job = await service.get_for_employer(auth, application_id)
    return RecruiterApplicationResponse(message="", application=await _detail(service, db, application, job))


@router.post(
    "/applications/{application_id}/transition", response_model=RecruiterApplicationResponse, summary="Move an applicant to a stage",
    description="`to` is one of shortlisted, assessment_invited, ai_interview_invited, recruiter_review, hr_interview — and only what the job's pipeline allows next. Offered, placed and "
    "rejected have their own steps; assessment and interview completion are recorded by the platform.", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit],
)
async def transition(application_id: ApplicationIdParam, body: TransitionRequest, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> RecruiterApplicationResponse:
    service = ApplicationService(db, settings)
    application, job = await service.get_for_employer(auth, application_id)
    application = await service.transition(auth, application, job, body.to, note=body.note, hr_interview_at=body.hr_interview_at)
    return RecruiterApplicationResponse(message="Moved.", application=await _detail(service, db, application, job))


@router.post("/applications/{application_id}/advance", response_model=RecruiterApplicationResponse, summary="Move an applicant to the next stage of this job's pipeline", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit])
async def advance(application_id: ApplicationIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> RecruiterApplicationResponse:
    service = ApplicationService(db, settings)
    application, job = await service.get_for_employer(auth, application_id)
    application = await service.advance(auth, application, job)
    return RecruiterApplicationResponse(message="Moved.", application=await _detail(service, db, application, job))


@router.post("/applications/{application_id}/notes", response_model=NoteResponse, status_code=201, summary="Add a private note (the candidate never sees it)", responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit])
async def add_note(application_id: ApplicationIdParam, body: NoteIn, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> NoteResponse:
    service = ApplicationService(db, settings)
    application, _ = await service.get_for_employer(auth, application_id)
    note = await service.add_note(auth, application, body.body)
    return NoteResponse(message="Noted.", note={"author_user_id": str(note.author_user_id), "body": note.body, "created_at": note.created_at.strftime("%Y-%m-%dT%H:%M:%SZ")})


@router.post(
    "/applications/{application_id}/offer", response_model=OfferResponse, status_code=201, summary="Extend an offer",
    description="From recruiter review (or the HR interview when the pipeline has one). The candidate has `valid_days` (7 by default) to answer; an unanswered offer expires and is closed as declined.",
    responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit],
)
async def extend_offer(application_id: ApplicationIdParam, body: OfferRequest, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> OfferResponse:
    applications = ApplicationService(db, settings)
    application, job = await applications.get_for_employer(auth, application_id)
    offer = await OfferService(db, settings).extend(
        auth, application, job, ctc=body.ctc, currency=body.currency, joining_date=body.joining_date, valid_days=body.valid_days, note=body.note, role_title=body.role_title
    )
    return OfferResponse(message="Offer extended.", offer=OfferOut.model_validate(offer))


@router.post(
    "/applications/{application_id}/place", response_model=RecruiterApplicationResponse, summary="Record that the candidate joined",
    description="Emits `candidate.placed`. When placements reach the job's openings, the job closes itself.", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit],
)
async def place(application_id: ApplicationIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> RecruiterApplicationResponse:
    service = ApplicationService(db, settings)
    application, job = await service.get_for_employer(auth, application_id)
    application = await service.place(auth, application, job)
    return RecruiterApplicationResponse(message="Placed.", application=await _detail(service, db, application, job))

