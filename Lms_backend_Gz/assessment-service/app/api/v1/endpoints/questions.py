from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    AuthoringRateLimit,
    CurrentAuth,
    DbSession,
    IdempotencyKeyHeader,
    QuestionIdParam,
    RequireAuthor,
    SettingsDep,
)
from app.api.presenters import question_list_item, question_out, version_out
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import ValidationFailedError
from app.schemas.common import QuestionQuery
from app.schemas.question import (
    QuestionBulkCreate,
    QuestionBulkResponse,
    QuestionBulkResult,
    QuestionCreate,
    QuestionListResponse,
    QuestionResponse,
    QuestionStatsOut,
    QuestionStatsResponse,
    QuestionUpdate,
    QuestionVersionsResponse,
    RejectNote,
    ReviewNote,
)
from app.services.question_service import QuestionService
from app.services.stats_service import StatsService

router = APIRouter(prefix="/questions", tags=["Question bank"])


@router.post(
    "",
    response_model=QuestionResponse,
    status_code=201,
    dependencies=[AuthoringRateLimit],
    summary="Create a question",
    description="Creates the question with its first version as a draft. `body` and `answer_key` depend on "
    "`question_type` (docs/API.md \"Question types\"). Platform authors (`content.author`) write the platform bank; "
    "an employer's members write that employer's bank, used only by its own hiring tests.",
    responses=errors(*AUTHENTICATED, 409),
)
async def create_question(
    data: QuestionCreate, auth: RequireAuthor, db: DbSession, settings: SettingsDep, key: IdempotencyKeyHeader
) -> QuestionResponse:
    question = await QuestionService(db, settings).create(data, auth, key)
    return QuestionResponse(message="Question created successfully.", question=question_out(question))


@router.post(
    "/bulk",
    response_model=QuestionBulkResponse,
    status_code=201,
    dependencies=[AuthoringRateLimit],
    summary="Import many questions",
    description="Each question is created or refused on its own; the response reports every outcome by position. "
    "Send an Idempotency-Key so a retried import is not applied twice.",
    responses=errors(*AUTHENTICATED, 409),
)
async def bulk_create_questions(
    data: QuestionBulkCreate, auth: RequireAuthor, db: DbSession, settings: SettingsDep, key: IdempotencyKeyHeader
) -> QuestionBulkResponse:
    outcome = await QuestionService(db, settings).bulk_create(data.questions, auth, key)
    results: list[QuestionBulkResult] = []
    for index, question, error in outcome:
        if question is not None:
            results.append(QuestionBulkResult(index=index, question_id=question.public_id))
        else:
            assert isinstance(error, ValidationFailedError)
            results.append(QuestionBulkResult(index=index, error=error.code, details=error.details))
    created = sum(1 for r in results if r.question_id is not None)
    return QuestionBulkResponse(message=f"{created} of {len(results)} questions imported.", created=created, failed=len(results) - created, results=results)


@router.get("", response_model=QuestionListResponse, summary="List questions in the bank", responses=errors(*AUTHENTICATED))
async def list_questions(
    query: Annotated[QuestionQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep
) -> QuestionListResponse:
    questions, versions, total, is_exact = await QuestionService(db, settings).list_questions(query, auth)
    return QuestionListResponse(
        message="Questions retrieved successfully.",
        questions=[question_list_item(q, versions[q.id]) for q in questions if q.id in versions],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get("/{question_id}", response_model=QuestionResponse, summary="Get a question with its versions", responses=errors(*AUTHENTICATED, 404))
async def get_question(question_id: QuestionIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> QuestionResponse:
    service = QuestionService(db, settings)
    question = await service.get(question_id, auth)
    return QuestionResponse(message="Question retrieved successfully.", question=question_out(question, await service.stats(question)))


@router.get("/{question_id}/versions", response_model=QuestionVersionsResponse, summary="Every version of a question", responses=errors(*AUTHENTICATED, 404))
async def question_versions(question_id: QuestionIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> QuestionVersionsResponse:
    question = await QuestionService(db, settings).get(question_id, auth)
    return QuestionVersionsResponse(message="Versions retrieved successfully.", versions=[version_out(v) for v in reversed(question.versions)])


@router.patch(
    "/{question_id}",
    response_model=QuestionResponse,
    dependencies=[AuthoringRateLimit],
    summary="Edit a question",
    description="Edits the working draft. On a published question the first edit opens a new draft version (a copy of "
    "the live one); the live version keeps serving until the draft is approved.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def update_question(
    question_id: QuestionIdParam, data: QuestionUpdate, auth: CurrentAuth, db: DbSession, settings: SettingsDep
) -> QuestionResponse:
    service = QuestionService(db, settings)
    question = await service.update(await service.get(question_id, auth), data, auth)
    return QuestionResponse(message="Question updated successfully.", question=question_out(question))


@router.post("/{question_id}/submit", response_model=QuestionResponse, summary="Submit the draft for review", responses=errors(*AUTHENTICATED, 404, 409))
async def submit_question(question_id: QuestionIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> QuestionResponse:
    service = QuestionService(db, settings)
    question = await service.submit(await service.get(question_id, auth), auth)
    return QuestionResponse(message="Question submitted for review.", question=question_out(question))


@router.post(
    "/{question_id}/approve",
    response_model=QuestionResponse,
    summary="Approve and publish the version in review",
    description="Needs `content.review` (an employer admin for an employer's question) and someone other than the author.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def approve_question(
    question_id: QuestionIdParam, data: ReviewNote, auth: CurrentAuth, db: DbSession, settings: SettingsDep
) -> QuestionResponse:
    service = QuestionService(db, settings)
    question = await service.approve(await service.get(question_id, auth), auth, data.note)
    return QuestionResponse(message="Question approved and published.", question=question_out(question))


@router.post("/{question_id}/reject", response_model=QuestionResponse, summary="Send the version in review back to draft", responses=errors(*AUTHENTICATED, 404, 409))
async def reject_question(
    question_id: QuestionIdParam, data: RejectNote, auth: CurrentAuth, db: DbSession, settings: SettingsDep
) -> QuestionResponse:
    service = QuestionService(db, settings)
    question = await service.reject(await service.get(question_id, auth), auth, data.note)
    return QuestionResponse(message="Question sent back to draft.", question=question_out(question))


@router.delete("/{question_id}/draft", response_model=QuestionResponse, summary="Discard an unpublished edit", responses=errors(*AUTHENTICATED, 404, 409))
async def discard_draft(question_id: QuestionIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> QuestionResponse:
    service = QuestionService(db, settings)
    question = await service.discard_draft(await service.get(question_id, auth), auth)
    return QuestionResponse(message="Draft edit discarded.", question=question_out(question))


@router.post("/{question_id}/retire", response_model=QuestionResponse, summary="Retire a question (no new papers use it)", responses=errors(*AUTHENTICATED, 404, 409))
async def retire_question(question_id: QuestionIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> QuestionResponse:
    service = QuestionService(db, settings)
    question = await service.retire(await service.get(question_id, auth), auth)
    return QuestionResponse(message="Question retired.", question=question_out(question))


@router.post("/{question_id}/restore", response_model=QuestionResponse, summary="Bring a retired question back", responses=errors(*AUTHENTICATED, 404))
async def restore_question(question_id: QuestionIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> QuestionResponse:
    service = QuestionService(db, settings)
    question = await service.restore(await service.get(question_id, auth), auth)
    return QuestionResponse(message="Question restored.", question=question_out(question))


@router.post(
    "/{question_id}/stats/recompute",
    response_model=QuestionStatsResponse,
    summary="Recompute difficulty index and discrimination now",
    description="Statistics are refreshed automatically after attempts; this forces it for one question.",
    responses=errors(*AUTHENTICATED, 404),
)
async def recompute_stats(question_id: QuestionIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> QuestionStatsResponse:
    question = await QuestionService(db, settings).get(question_id, auth)
    stats = await StatsService(db, settings).recompute_question(question)
    return QuestionStatsResponse(message="Statistics recomputed.", stats=QuestionStatsOut.model_validate(stats) if stats else None)
