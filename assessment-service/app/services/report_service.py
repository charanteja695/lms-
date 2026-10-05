"""Who can see which attempts, the grading queue and the per-test reports (results, analytics, plagiarism, CSV)."""

import csv
import io
from collections.abc import AsyncIterator
from typing import Any

from lms_common.pagination import paginate
from sqlalchemy import Select, func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import PermissionDeniedError
from app.core.security import AccessTokenClaims
from app.domain.enums import AttemptResult, AttemptStatus, GradingStatus, IntegrityStatus
from app.models.attempt import Attempt, AttemptAnswer, AttemptQuestion, CodingSubmission
from app.models.question import Question, QuestionStats, QuestionVersion
from app.models.test import Test
from app.permissions.policy import (
    can_manage_exams,
    can_review_platform,
    is_employer_member,
    is_institution_staff,
    is_student,
)
from app.schemas.common import AttemptQuery, GradingQueueQuery

_EXPORT_PAGE = 500


def scope_attempts(stmt: Select[Any], auth: AccessTokenClaims) -> Select[Any]:
    """Restrict a query over ``Attempt`` (joined to ``Test``) to what the caller may see."""
    if is_student(auth):
        return stmt.where(Attempt.user_id == auth.user_id)
    stmt = stmt.where(Attempt.status != AttemptStatus.NOT_STARTED)
    if can_manage_exams(auth) or can_review_platform(auth):
        return stmt
    if is_institution_staff(auth):  # their own students, on platform tests (an employer's hiring test is private to it)
        return stmt.where(Attempt.organization_id == auth.organization_id, Test.organization_id.is_(None))
    if is_employer_member(auth):
        return stmt.where(Test.organization_id == auth.organization_id)
    raise PermissionDeniedError()


def scope_answers_to_grade(stmt: Select[Any], auth: AccessTokenClaims) -> Select[Any]:
    """Answers awaiting a grade that the caller may grade (see ``can_grade_attempt``)."""
    if can_manage_exams(auth):
        return stmt
    if is_employer_member(auth):
        return stmt.where(Test.organization_id == auth.organization_id)
    if is_institution_staff(auth):
        return stmt.where(Attempt.organization_id == auth.organization_id, Test.organization_id.is_(None))
    raise PermissionDeniedError()


class ReportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_attempts(
        self, query: AttemptQuery, auth: AccessTokenClaims, *, test_public_id: int | None = None
    ) -> tuple[list[Attempt], int, bool]:
        stmt = scope_attempts(select(Attempt).join(Test, Test.id == Attempt.test_id), auth)
        if test_public_id is not None:
            stmt = stmt.where(Attempt.test_public_id == test_public_id)
        elif query.test_id:
            stmt = stmt.where(Attempt.test_public_id == query.test_id)
        if query.user_id and not is_student(auth):
            stmt = stmt.where(Attempt.user_id == query.user_id)
        if query.status:
            stmt = stmt.where(Attempt.status == query.status)
        if query.result:
            stmt = stmt.where(Attempt.result == query.result)
        if query.integrity_status:
            stmt = stmt.where(Attempt.integrity_status == query.integrity_status)
        if query.plagiarism_flagged is not None:
            stmt = stmt.where(Attempt.plagiarism_flagged.is_(query.plagiarism_flagged))
        stmt = stmt.order_by(Attempt.created_at.asc() if query.sort_order == "asc" else Attempt.created_at.desc(), Attempt.id)
        return await paginate(self.db, stmt, query.page, query.per_page)

    # ------------------------------------------------------------------ grading queue

    async def grading_queue(self, query: GradingQueueQuery, auth: AccessTokenClaims) -> tuple[list[dict[str, Any]], int, bool]:
        stmt = (
            select(AttemptAnswer)
            .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
            .join(Test, Test.id == Attempt.test_id)
            .where(AttemptAnswer.grading_status == GradingStatus.PENDING_MANUAL, Attempt.status.in_([AttemptStatus.GRADING, AttemptStatus.GRADED]))
        )
        stmt = scope_answers_to_grade(stmt, auth)
        if query.test_id:
            stmt = stmt.where(Attempt.test_public_id == query.test_id)
        stmt = stmt.order_by(Attempt.submitted_at.asc() if query.sort_order == "asc" else Attempt.submitted_at.desc(), AttemptAnswer.id)
        answers, total, exact = await paginate(self.db, stmt, query.page, query.per_page)
        items: list[dict[str, Any]] = []
        for answer in answers:
            attempt = (await self.db.execute(select(Attempt).where(Attempt.id == answer.attempt_id))).scalar_one()
            row = (
                await self.db.execute(
                    select(AttemptQuestion.marks, QuestionVersion.text, QuestionVersion.body, Question.question_type)
                    .join(QuestionVersion, QuestionVersion.id == AttemptQuestion.question_version_id)
                    .join(Question, Question.id == AttemptQuestion.question_id)
                    .where(AttemptQuestion.attempt_id == answer.attempt_id, AttemptQuestion.question_public_id == answer.question_public_id)
                )
            ).one()
            items.append(
                {
                    "attempt_id": attempt.public_id,
                    "test_id": attempt.test_public_id,
                    "user_id": attempt.user_id,
                    "question_id": answer.question_public_id,
                    "question_type": row[3],
                    "text": row[1],
                    "marks": row[0],
                    "rubric": (row[2] or {}).get("rubric") or [],
                    "response": answer.response,
                    "submitted_at": attempt.submitted_at,
                }
            )
        return items, total, exact

    # ------------------------------------------------------------------ per-test reports

    async def analytics(self, test: Test) -> dict[str, Any]:
        by_status = {
            status: int(count)
            for status, count in (
                await self.db.execute(select(Attempt.status, func.count()).where(Attempt.test_id == test.id).group_by(Attempt.status))
            ).all()
        }
        counted = (Attempt.test_id == test.id, Attempt.status == AttemptStatus.GRADED, Attempt.result != AttemptResult.INVALIDATED)
        rows = (
            await self.db.execute(select(Attempt.percent, Attempt.result, Attempt.started_at, Attempt.submitted_at).where(*counted).limit(10_000))
        ).all()
        percents = [float(percent) for percent, *_ in rows if percent is not None]
        decided = [result for _, result, *_ in rows if result in (AttemptResult.PASSED, AttemptResult.FAILED)]
        minutes = [(submitted - started).total_seconds() / 60 for _, _, started, submitted in rows if started and submitted]
        bins = [{"from": low, "to": low + 10, "count": 0} for low in range(0, 100, 10)]
        for percent in percents:
            bins[min(int(percent // 10), 9)]["count"] += 1
        flagged = (
            await self.db.execute(select(func.count()).select_from(Attempt).where(Attempt.test_id == test.id, Attempt.plagiarism_flagged.is_(True)))
        ).scalar_one()
        pending_integrity = (
            await self.db.execute(
                select(func.count()).select_from(Attempt).where(
                    Attempt.test_id == test.id,
                    Attempt.status == AttemptStatus.GRADED,
                    Attempt.integrity_status.in_([IntegrityStatus.PENDING, IntegrityStatus.FLAGGED, IntegrityStatus.UNDER_REVIEW]),
                )
            )
        ).scalar_one()
        served = (
            await self.db.execute(
                select(Question.public_id, Question.question_type, func.count(), QuestionStats.difficulty_index, QuestionStats.discrimination, QuestionStats.sample_size)
                .select_from(AttemptQuestion)
                .join(Attempt, Attempt.id == AttemptQuestion.attempt_id)
                .join(Question, Question.id == AttemptQuestion.question_id)
                .outerjoin(QuestionStats, QuestionStats.question_id == Question.id)
                .where(Attempt.test_id == test.id)
                .group_by(Question.public_id, Question.question_type, QuestionStats.difficulty_index, QuestionStats.discrimination, QuestionStats.sample_size)
                .order_by(func.count().desc())
                .limit(200)
            )
        ).all()
        return {
            "attempts": by_status,
            "graded": len(rows),
            "average_percent": round(sum(percents) / len(percents), 2) if percents else None,
            "pass_rate_percent": round(100 * sum(1 for r in decided if r == AttemptResult.PASSED) / len(decided), 2) if decided else None,
            "average_minutes": round(sum(minutes) / len(minutes), 1) if minutes else None,
            "distribution": bins,
            "plagiarism_flagged": int(flagged),
            "integrity_pending": int(pending_integrity),
            "questions": [
                {
                    "question_id": str(public_id),
                    "question_type": qtype,
                    "times_served": int(times),
                    "difficulty_index": difficulty,
                    "discrimination": discrimination,
                    "sample_size": sample,
                }
                for public_id, qtype, times, difficulty, discrimination, sample in served
            ],
        }

    async def plagiarism(self, test: Test) -> list[dict[str, Any]]:
        rows = (
            await self.db.execute(
                select(CodingSubmission)
                .join(Attempt, Attempt.id == CodingSubmission.attempt_id)
                .where(Attempt.test_id == test.id, CodingSubmission.flagged.is_(True))
                .order_by(CodingSubmission.similarity_percent.desc().nulls_last())
                .limit(500)
            )
        ).scalars()
        return [
            {
                "attempt_id": row.attempt_public_id,
                "user_id": row.user_id,
                "question_id": row.question_public_id,
                "language": row.language,
                "verdict": row.verdict,
                "similarity_percent": row.similarity_percent,
                "similar_to_submission_id": row.similar_to_submission_id,
                "code_submission_id": row.code_submission_id,
            }
            for row in rows
        ]


async def export_results_csv(sessionmaker: async_sessionmaker[AsyncSession], test_id: Any) -> AsyncIterator[str]:
    """Every started attempt of a test as CSV, in pages, so a 200k-student exam streams in constant memory."""
    columns = ["attempt_id", "user_id", "organization_id", "attempt_no", "status", "result", "score", "max_score", "percent", "integrity_status", "plagiarism_flagged", "submitted_at"]
    header = io.StringIO()
    csv.writer(header).writerow(columns)
    yield header.getvalue()
    last: tuple[Any, Any] | None = None
    while True:
        async with sessionmaker() as db:
            stmt = select(Attempt).where(Attempt.test_id == test_id, Attempt.status != AttemptStatus.NOT_STARTED)
            if last is not None:
                stmt = stmt.where(tuple_(Attempt.created_at, Attempt.id) > tuple_(last[0], last[1]))
            page = list((await db.execute(stmt.order_by(Attempt.created_at, Attempt.id).limit(_EXPORT_PAGE))).scalars())
        if not page:
            return
        out = io.StringIO()
        writer = csv.writer(out)
        for attempt in page:
            writer.writerow(
                [
                    attempt.public_id,
                    attempt.user_id,
                    attempt.organization_id or "",
                    attempt.attempt_no,
                    attempt.status,
                    attempt.result,
                    attempt.score if attempt.score is not None else "",
                    attempt.max_score if attempt.max_score is not None else "",
                    attempt.percent if attempt.percent is not None else "",
                    attempt.integrity_status,
                    attempt.plagiarism_flagged,
                    attempt.submitted_at.strftime("%Y-%m-%dT%H:%M:%SZ") if attempt.submitted_at else "",
                ]
            )
        yield out.getvalue()
        last = (page[-1].created_at, page[-1].id)
