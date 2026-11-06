"""Builds the attempt responses: the state a student's client needs, the paper with their answers, and results.

What a student may see and when is decided here (presentation only; the rules that produce the numbers live in the
services): the paper is shown only while the attempt runs, and after it ends only through the result, once released.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.presenters import attempt_state, section_states, wants_review
from app.core.security import AccessTokenClaims
from app.domain.enums import AttemptStatus
from app.models.attempt import Attempt, AttemptQuestion
from app.models.question import Question, QuestionVersion
from app.models.test import Test, TestSchedule
from app.permissions.policy import can_view_attempt
from app.schemas.attempt import AttemptStateOut, PaperQuestionOut, ResultOut, ReviewQuestionOut
from app.services import clock
from app.services.answer_service import AnswerService
from app.services.attempt_service import AttemptService


async def state_of(service: AttemptService, attempt: Attempt, test: Test | None = None) -> AttemptStateOut:
    test = test or await service.test_of(attempt, with_sections=True)
    sections = []
    if attempt.sections:
        limits = {s.position: s.time_limit_minutes for s in test.sections}
        titles = {s.position: s.title for s in test.sections}
        sections = section_states(service._clocks(attempt, list(test.sections)), titles, limits)
    opens_at = None
    if attempt.status == AttemptStatus.NOT_STARTED and attempt.schedule_id is not None:
        schedule = await service.db.get(TestSchedule, attempt.schedule_id)
        opens_at = schedule.starts_at if schedule else None
    return attempt_state(attempt, test, sections=sections, opens_at=opens_at)


async def paper_view(db: AsyncSession, service: AttemptService, answers: AnswerService, attempt: Attempt, test: Test) -> list[PaperQuestionOut]:
    """The questions and this student's answers, only while the attempt runs."""
    if attempt.status != AttemptStatus.IN_PROGRESS:
        return []
    paper = await service.paper(attempt.public_id, attempt.id)
    if attempt.sections:  # a per-section test reveals a section only once it has started
        sections = service._clocks(attempt, list(test.sections))
        current = clock.current(sections)
        if current is not None:
            paper = [q for q in paper if q["section_position"] <= current.position]
    mine = await answers.merged(attempt)
    return [PaperQuestionOut(**q, answer=mine.get(int(q["question_id"]))) for q in paper]


async def result_view(
    db: AsyncSession, service: AttemptService, answers: AnswerService, attempt: Attempt, test: Test, viewer: AccessTokenClaims
) -> ResultOut:
    owner = attempt.user_id == viewer.user_id
    released = attempt.results_visible_at is not None
    base: dict[str, Any] = {
        "attempt_id": attempt.public_id,
        "test_id": test.public_id,
        "test_title": test.title,
        "status": attempt.status,
        "released": released,
        "submitted_at": attempt.submitted_at,
    }
    staff = not owner and can_view_attempt(
        viewer, attempt_user_id=attempt.user_id, attempt_organization_id=attempt.organization_id, test_owner_id=test.organization_id
    )
    if attempt.status != AttemptStatus.GRADED:
        return ResultOut(**base, message="Your answers were submitted and are being graded." if owner else "This attempt is still being graded.")
    if not released and not staff:
        return ResultOut(**base, message="Results have not been released yet.")

    full = {
        **base,
        "result": attempt.result,
        "score": attempt.score,
        "max_score": attempt.max_score,
        "percent": attempt.percent,
        "pass_mark_percent": test.pass_mark_percent,
        "integrity_status": attempt.integrity_status,
        "released_at": attempt.results_visible_at,
    }
    if not (staff or wants_review(test)):
        return ResultOut(**full)
    return ResultOut(**full, questions=await _review(db, answers, attempt, with_keys=True))


async def _review(db: AsyncSession, answers: AnswerService, attempt: Attempt, *, with_keys: bool) -> list[ReviewQuestionOut]:
    rows = await db.execute(
        select(AttemptQuestion, Question.question_type, QuestionVersion.text, QuestionVersion.body, QuestionVersion.answer_key, QuestionVersion.explanation)
        .join(QuestionVersion, QuestionVersion.id == AttemptQuestion.question_version_id)
        .join(Question, Question.id == AttemptQuestion.question_id)
        .where(AttemptQuestion.attempt_id == attempt.id)
        .order_by(AttemptQuestion.position)
    )
    graded = await answers_by_question(db, attempt)
    review: list[ReviewQuestionOut] = []
    for aq, qtype, text, body, key, explanation in rows.all():
        row = graded.get(aq.question_public_id)
        review.append(
            ReviewQuestionOut(
                question_id=aq.question_public_id,
                position=aq.position,
                question_type=qtype,
                text=text,
                body=body,
                marks=aq.marks,
                marks_awarded=row.marks_awarded if row else None,
                is_correct=row.is_correct if row else None,
                grading_status=row.grading_status if row else None,
                feedback=row.feedback if row else None,
                rubric_scores=row.rubric_scores if row else None,
                response=row.response if row else None,
                answer_key=key if with_keys else None,
                explanation=explanation if with_keys else None,
            )
        )
    return review


async def answers_by_question(db: AsyncSession, attempt: Attempt) -> dict[int, Any]:
    from app.services.answer_store import AnswerStore

    return await AnswerStore(db).load(attempt.id)
