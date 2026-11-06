"""Authors' tools (feedback, offline evaluation), index administration, escalations and the internal transcript API."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder
from lms_common.pagination import paginate
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import (
    AuthoringRateLimit,
    DbSession,
    EscalationIdParam,
    EvalRunIdParam,
    EvalSetIdParam,
    GatewayDep,
    IndexCacheDep,
    RequireAuthor,
    RequireIndexManager,
    RequireIndexReader,
    RequireInternalCaller,
    RequireSupportManager,
    SettingsDep,
)
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ids import parse_public_id
from app.domain.enums import EscalationStatus
from app.models.conversation import Conversation, Escalation
from app.models.refs import CourseVersionRef
from app.schemas.admin import (
    DownvotedOut,
    DownvotedResponse,
    EscalationListResponse,
    EscalationOut,
    EscalationResponse,
    EvalCaseCreate,
    EvalCaseOut,
    EvalCaseResponse,
    EvalRunCreate,
    EvalRunOut,
    EvalRunResponse,
    EvalSetCreate,
    EvalSetDetailResponse,
    EvalSetListResponse,
    EvalSetOut,
    EvalSetResponse,
    FeedbackSummaryOut,
    FeedbackSummaryResponse,
    IndexStatusResponse,
    IndexVersionOut,
    ReindexIn,
)
from app.schemas.tutor import ConversationDetailOut, ConversationDetailResponse
from app.services.escalation_service import EscalationService
from app.services.eval_service import EvalService
from app.services.feedback_service import FeedbackService
from app.services.index_service import IndexService

router = APIRouter(tags=["Operations"])


def _course(value: str) -> int:
    number = parse_public_id(value)
    if number is None:
        raise NotFoundError("Course not found.", code="COURSE_NOT_FOUND")
    return number


# ------------------------------------------------------------------ feedback
@router.get("/feedback/summary", response_model=FeedbackSummaryResponse, summary="Thumbs up/down totals for a course", responses=errors(*AUTHENTICATED))
async def feedback_summary(auth: RequireAuthor, db: DbSession, course_id: Annotated[str, Query()]) -> FeedbackSummaryResponse:
    data = await FeedbackService(db).summary(_course(course_id))
    return FeedbackSummaryResponse(message="", summary=FeedbackSummaryOut.model_validate(data))


@router.get("/feedback/downvoted", response_model=DownvotedResponse, summary="Answers students marked unhelpful (without who asked)", responses=errors(*AUTHENTICATED))
async def feedback_downvoted(auth: RequireAuthor, db: DbSession, course_id: Annotated[str, Query()], limit: Annotated[int, Query(ge=1, le=100)] = 25) -> DownvotedResponse:
    items = await FeedbackService(db).downvoted(_course(course_id), limit)
    return DownvotedResponse(message="", items=[DownvotedOut.model_validate(i) for i in items])


# ------------------------------------------------------------------ offline evaluation
@router.post("/eval-sets", response_model=EvalSetResponse, status_code=201, dependencies=[AuthoringRateLimit], summary="Create an evaluation set for a course", responses=errors(*AUTHENTICATED))
async def create_eval_set(body: EvalSetCreate, auth: RequireAuthor, db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCacheDep) -> EvalSetResponse:
    eval_set = await EvalService(db, settings, gateway, cache).create_set(course_id=body.course_id, name=body.name, created_by=auth.user_id)
    return EvalSetResponse(message="Evaluation set created.", eval_set=EvalSetOut.model_validate(eval_set))


@router.get("/eval-sets", response_model=EvalSetListResponse, summary="A course's evaluation sets, newest first", responses=errors(*AUTHENTICATED))
async def list_eval_sets(auth: RequireAuthor, db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCacheDep, course_id: Annotated[str, Query()]) -> EvalSetListResponse:
    sets = await EvalService(db, settings, gateway, cache).list_sets(_course(course_id))
    return EvalSetListResponse(message="", eval_sets=[EvalSetOut.model_validate(s) for s in sets])


@router.get("/eval-sets/{eval_set_id}", response_model=EvalSetDetailResponse, summary="An evaluation set with its questions and runs", responses=errors(*AUTHENTICATED, 404))
async def get_eval_set(eval_set_id: EvalSetIdParam, auth: RequireAuthor, db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCacheDep) -> EvalSetDetailResponse:
    service = EvalService(db, settings, gateway, cache)
    eval_set = await service.get_set(eval_set_id)
    return EvalSetDetailResponse(
        message="", eval_set=EvalSetOut.model_validate(eval_set), cases=[EvalCaseOut.model_validate(c) for c in await service.cases(eval_set)],
        runs=[EvalRunOut.model_validate(r) for r in await service.runs(eval_set)],
    )


@router.post("/eval-sets/{eval_set_id}/cases", response_model=EvalCaseResponse, status_code=201, dependencies=[AuthoringRateLimit], summary="Add a question and the lesson(s) that answer it", responses=errors(*AUTHENTICATED, 404))
async def add_eval_case(eval_set_id: EvalSetIdParam, body: EvalCaseCreate, auth: RequireAuthor, db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCacheDep) -> EvalCaseResponse:
    service = EvalService(db, settings, gateway, cache)
    case = await service.add_case(await service.get_set(eval_set_id), question=body.question, expected_item_ids=list(body.expected_item_ids))
    return EvalCaseResponse(message="Question added.", case=EvalCaseOut.model_validate(case))


@router.post(
    "/eval-sets/{eval_set_id}/runs", response_model=EvalRunResponse, status_code=201, dependencies=[AuthoringRateLimit], summary="Run the set against the course's current index",
    description="Measures the retriever: hit@k and MRR of the expected lessons. `method` says whether dense (embedding) or lexical retrieval was used.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def run_eval_set(eval_set_id: EvalSetIdParam, body: EvalRunCreate, auth: RequireAuthor, db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCacheDep) -> EvalRunResponse:
    service = EvalService(db, settings, gateway, cache)
    run = await service.run(await service.get_set(eval_set_id), version_id=body.version_id, triggered_by=auth.user_id, top_k=body.top_k)
    return EvalRunResponse(message="Evaluation finished.", run=EvalRunOut.model_validate(run))


@router.get("/eval-runs/{run_id}", response_model=EvalRunResponse, summary="One evaluation run", responses=errors(*AUTHENTICATED, 404))
async def get_eval_run(run_id: EvalRunIdParam, auth: RequireAuthor, db: DbSession, settings: SettingsDep, gateway: GatewayDep, cache: IndexCacheDep) -> EvalRunResponse:
    return EvalRunResponse(message="", run=EvalRunOut.model_validate(await EvalService(db, settings, gateway, cache).get_run(run_id)))


# ------------------------------------------------------------------ index
@router.get("/index/status", response_model=IndexStatusResponse, summary="Indexing status of a course's versions", responses=errors(*AUTHENTICATED))
async def index_status(auth: RequireIndexReader, db: DbSession, settings: SettingsDep, course_id: Annotated[str, Query()]) -> IndexStatusResponse:
    return IndexStatusResponse(message="", versions=[IndexVersionOut.model_validate(v) for v in await IndexService(db, settings).status(_course(course_id))])


@router.post("/index/reindex", response_model=IndexStatusResponse, status_code=202, summary="Embed a version again (after an embedding-model change)", responses=errors(*AUTHENTICATED, 404))
async def reindex(body: ReindexIn, auth: RequireIndexManager, db: DbSession, settings: SettingsDep) -> IndexStatusResponse:

    ref = await db.get(CourseVersionRef, body.version_id)
    if ref is None:
        raise NotFoundError("Version not found.", code="VERSION_NOT_FOUND")
    service = IndexService(db, settings)
    await service.reindex(body.version_id)
    return IndexStatusResponse(message="Re-embedding queued.", versions=[IndexVersionOut.model_validate(v) for v in await service.status(ref.course_id)])


# ------------------------------------------------------------------ escalations
@router.get("/escalations", response_model=EscalationListResponse, summary="Hand-offs to support", responses=errors(*AUTHENTICATED))
async def list_escalations(
    auth: RequireSupportManager, db: DbSession, status: Annotated[EscalationStatus | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EscalationListResponse:
    stmt = select(Escalation).order_by(Escalation.created_at.desc(), Escalation.id)
    if status:
        stmt = stmt.where(Escalation.status == status)
    rows, total, exact = await paginate(db, stmt, page, per_page)
    context = PageContext.build(page=page, per_page=per_page, total=total, is_exact=exact, sort_column="created_at", sort_order=SortOrder.DESC)
    return EscalationListResponse(message="", escalations=[EscalationOut.model_validate(r) for r in rows], page_context=context)


@router.post("/escalations/{escalation_id}/retry", response_model=EscalationResponse, summary="Re-queue a failed hand-off", responses=errors(*AUTHENTICATED, 404, 409))
async def retry_escalation(escalation_id: EscalationIdParam, auth: RequireSupportManager, db: DbSession, settings: SettingsDep) -> EscalationResponse:
    escalation = (await db.execute(select(Escalation).where(Escalation.public_id == escalation_id))).scalar_one_or_none()
    if escalation is None:
        raise NotFoundError("Escalation not found.", code="ESCALATION_NOT_FOUND")
    if escalation.status != EscalationStatus.FAILED:
        raise ConflictError("Only a failed hand-off can be retried.", code="NOT_FAILED")
    return EscalationResponse(message="Queued again.", escalation=EscalationOut.model_validate(await EscalationService(db, settings).retry(escalation)))


# ------------------------------------------------------------------ internal (support-service)
internal = APIRouter(prefix="/internal", tags=["Internal"], dependencies=[RequireInternalCaller])


@internal.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse, summary="A conversation's transcript, for the agent who received its ticket", responses=errors(401, 403, 404))
async def internal_transcript(conversation_id: str, db: DbSession) -> ConversationDetailResponse:
    number = parse_public_id(conversation_id)
    conversation = None
    if number is not None:
        conversation = (
            await db.execute(select(Conversation).where(Conversation.public_id == number, Conversation.deleted_at.is_(None)).options(selectinload(Conversation.messages)))
        ).scalar_one_or_none()
    if conversation is None:
        raise NotFoundError("Conversation not found.", code="CONVERSATION_NOT_FOUND")
    return ConversationDetailResponse(message="", conversation=ConversationDetailOut.model_validate(conversation))
