from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import AttemptIdParam, CurrentAuth, DbSession, QuestionIdParam, RedisDep, SettingsDep
from app.api.responses import AUTHENTICATED, errors
from app.schemas.attempt import (
    AttemptListItem,
    GradedAnswerOut,
    GradedAnswerResponse,
    GradeIn,
    GradingQueueItem,
    GradingQueueResponse,
)
from app.schemas.common import GradingQueueQuery
from app.services.grading_service import GradingService
from app.services.report_service import ReportService

router = APIRouter(tags=["Grading"])


@router.get(
    "/grading/queue",
    response_model=GradingQueueResponse,
    summary="Answers waiting for a human grade",
    description="Subjective and file answers, and coding answers that could not be judged automatically. Exam managers "
    "see all; institution staff see their own students' (platform tests); an employer sees its hiring tests'.",
    responses=errors(*AUTHENTICATED),
)
async def grading_queue(query: Annotated[GradingQueueQuery, Query()], auth: CurrentAuth, db: DbSession) -> GradingQueueResponse:
    items, total, is_exact = await ReportService(db).grading_queue(query, auth)
    return GradingQueueResponse(
        message="Grading queue retrieved successfully.",
        items=[GradingQueueItem(**item) for item in items],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="submitted_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.put(
    "/attempts/{attempt_id}/answers/{question_id}/grade",
    response_model=GradedAnswerResponse,
    summary="Grade an answer",
    description="Give per-criterion `rubric_scores` (questions with a rubric) or `marks`. When the last outstanding "
    "answer is graded the attempt is completed and its result decided. Exam managers may also override an automatic "
    "grade, and must then give `feedback` saying why; the override is audited.",
    responses=errors(*AUTHENTICATED, 403, 404, 409, 422),
)
async def grade_answer(
    attempt_id: AttemptIdParam, question_id: QuestionIdParam, data: GradeIn, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> GradedAnswerResponse:
    service = GradingService(db, settings, redis)
    answer = await service.manual_grade(
        attempt_id, question_id, auth, marks=data.marks, rubric_scores=data.rubric_scores, feedback=data.feedback
    )
    attempt = await service.attempts.get(attempt_id)
    return GradedAnswerResponse(
        message="Answer graded.",
        answer=GradedAnswerOut(
            question_id=answer.question_public_id,
            marks_awarded=answer.marks_awarded,
            max_marks=answer.max_marks,
            grading_status=answer.grading_status,
            feedback=answer.feedback,
            rubric_scores=answer.rubric_scores,
        ),
        attempt=AttemptListItem.model_validate(attempt),
    )
