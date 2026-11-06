"""A company's screening interviews: the transcript, the AI's evaluation, a person's review (confirm or override — never automatic; docs/PRODUCT.md
§5.8 "Human decision required in hiring"), a re-run of a failed evaluation, and appeals (decided by someone other than who reviewed it)."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import DbSession, GatewayDep, InterviewIdParam, RequireEmployerOrManager, SettingsDep, WriteRateLimit
from app.api.presenters import appeal_out, employer_interview_detail, employer_interview_out
from app.api.responses import AUTHENTICATED, errors
from app.core.ids import parse_public_id
from app.domain.enums import InterviewStatus
from app.schemas.interview import (
    AppealPage,
    AppealResponse,
    DecideAppealRequest,
    EmployerInterviewDetailResponse,
    EmployerInterviewPage,
    EmployerInterviewResponse,
    OpenAppealOut,
    ReviewRequest,
)
from app.services.evaluation_service import EvaluationService
from app.services.interview_service import InterviewService
from app.services.review_service import ReviewService

router = APIRouter(prefix="/employer/interviews", tags=["Interviews (employer)"])
appeals_router = APIRouter(prefix="/employer/appeals", tags=["Appeals"])


@router.get("", response_model=EmployerInterviewPage, summary="Screening interviews", responses=errors(*AUTHENTICATED))
async def list_interviews(
    auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep, status: Annotated[InterviewStatus | None, Query()] = None,
    application_id: Annotated[str | None, Query()] = None, job_id: Annotated[str | None, Query()] = None, page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EmployerInterviewPage:
    interviews, total = await InterviewService(db, settings).list_for_employer(
        auth, status=status.value if status else None, application_id=parse_public_id(application_id) if application_id else None, job_id=parse_public_id(job_id) if job_id else None,
        page=page, per_page=per_page,
    )
    return EmployerInterviewPage(
        message="", interviews=[employer_interview_out(i) for i in interviews],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


@router.get("/{interview_id}", response_model=EmployerInterviewDetailResponse, summary="An interview's transcript and evaluation", responses=errors(*AUTHENTICATED))
async def get_interview(interview_id: InterviewIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> EmployerInterviewDetailResponse:
    service = InterviewService(db, settings)
    interview = await service.get_for_employer(auth, interview_id)
    turns = await service.turns(interview)
    evaluation = await EvaluationService(db, settings, None).for_interview(interview)
    return EmployerInterviewDetailResponse(message="", interview=employer_interview_detail(interview, turns, evaluation))


@router.post(
    "/{interview_id}/review", response_model=EmployerInterviewResponse, summary="Confirm or override the AI's recommendation", responses=errors(*AUTHENTICATED, 409, 422),
    description="Send no recommendation to confirm the AI's; send one to override it (a note saying why is then required). Optionally releases the candidate's feedback.",
    dependencies=[WriteRateLimit],
)
async def review_interview(interview_id: InterviewIdParam, body: ReviewRequest, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> EmployerInterviewResponse:
    service = InterviewService(db, settings)
    interview = await ReviewService(db, settings).review(auth, await service.get_for_employer(auth, interview_id), recommendation=body.recommendation, note=body.note, release_feedback=body.release_feedback)
    return EmployerInterviewResponse(message="Recorded.", interview=employer_interview_out(interview))


@router.post(
    "/{interview_id}/evaluate", response_model=EmployerInterviewResponse, summary="Re-run the evaluation", responses=errors(*AUTHENTICATED, 409),
    description="For a failed evaluation, or after the prompt has changed. Runs in the background; poll the interview to see the result.", dependencies=[WriteRateLimit],
)
async def rerun_evaluation(interview_id: InterviewIdParam, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep, gateway: GatewayDep) -> EmployerInterviewResponse:
    service = InterviewService(db, settings)
    interview = await service.get_for_employer(auth, interview_id)
    await EvaluationService(db, settings, gateway).rerun(interview)
    return EmployerInterviewResponse(message="Re-evaluation queued.", interview=employer_interview_out(interview))


@appeals_router.get("", response_model=AppealPage, summary="Open appeals", responses=errors(*AUTHENTICATED))
async def list_open_appeals(
    auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep, page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AppealPage:
    rows, total = await ReviewService(db, settings).open_appeals(auth, page=page, per_page=per_page)
    return AppealPage(
        message="", appeals=[OpenAppealOut(**appeal_out(a, i.public_id).model_dump(), interview=employer_interview_out(i)) for a, i in rows],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.ASC),
    )


@router.post(
    "/{interview_id}/appeal/decide", response_model=AppealResponse, summary="Decide an appeal", responses=errors(*AUTHENTICATED, 403, 409, 422),
    description="Someone other than the person who reviewed the interview decides it (a careers manager may always). Upholding grants a retake.",
    dependencies=[WriteRateLimit],
)
async def decide_appeal(interview_id: InterviewIdParam, body: DecideAppealRequest, auth: RequireEmployerOrManager, db: DbSession, settings: SettingsDep) -> AppealResponse:
    service = InterviewService(db, settings)
    interview = await service.get_for_employer(auth, interview_id)
    appeal = await ReviewService(db, settings).decide(auth, interview, uphold=body.uphold, note=body.note)
    return AppealResponse(message="Decision recorded.", appeal=appeal_out(appeal, interview.public_id))
