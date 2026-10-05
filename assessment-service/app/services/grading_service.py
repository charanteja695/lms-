"""Grading (docs/PRODUCT.md §5.1): auto for objective answers, code-execution-service for coding/SQL, people for
subjective and file answers.

A submitted attempt is a queue row: a grader claims it (``FOR UPDATE SKIP LOCKED``, with a lease, exactly as
code-execution-service claims its jobs), scores what it can at once, queues coding answers for judging, and leaves
the attempt in ``grading`` until every outstanding answer has a grade. The last grade to arrive completes the
attempt — whether that was a verdict event, a reconciliation poll or a person — and hands it to the result rules.
"""

import logging
import uuid
from datetime import timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import (
    AUTO_GRADED_TYPES,
    JUDGED_TYPES,
    AttemptStatus,
    CodingStatus,
    GradingStatus,
    QuestionType,
)
from app.grading.objective import Grade, grade_judged, grade_objective, grade_rubric, round_marks, unanswered
from app.models.attempt import Attempt, AttemptAnswer, AttemptEvent, AttemptQuestion, CodingSubmission
from app.models.question import Question, QuestionVersion
from app.models.test import Test
from app.permissions.policy import can_grade_attempt, can_manage_exams
from app.services.answer_store import AnswerStore
from app.services.attempt_service import AttemptService, attempt_event_payload
from app.services.outbox import write_event
from app.services.result_service import ResultService

logger = logging.getLogger(__name__)

_PENDING = (GradingStatus.PENDING_JUDGE, GradingStatus.PENDING_MANUAL)


def coding_reference(attempt_public_id: int, question_public_id: int) -> str:
    return f"attempt:{attempt_public_id}:{question_public_id}"


class GradingService:
    def __init__(self, db: AsyncSession, settings: Settings, redis: Redis | None = None) -> None:
        self.db = db
        self.settings = settings
        self.redis = redis
        self.attempts = AttemptService(db, settings, redis)
        self.results = ResultService(db, settings, redis)

    # ------------------------------------------------------------------ the queue

    async def claim(self, limit: int) -> list[int]:
        """Take up to ``limit`` submitted attempts, oldest first, and lease them. Returns their public ids."""
        now = utcnow()
        rows = (
            await self.db.execute(
                select(Attempt)
                .where(
                    Attempt.status == AttemptStatus.SUBMITTED,
                    Attempt.grading_available_at <= now,
                    Attempt.grading_attempts < self.settings.JOB_MAX_ATTEMPTS,
                )
                .order_by(Attempt.grading_available_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars()
        claimed: list[int] = []
        for attempt in rows:
            attempt.grading_attempts += 1
            attempt.grading_available_at = now + timedelta(seconds=self.settings.JOB_LEASE_SECONDS)
            claimed.append(attempt.public_id)
        await self.db.commit()
        return claimed

    async def queue_depth(self) -> dict[str, int]:
        waiting = (
            await self.db.execute(select(func.count()).select_from(Attempt).where(Attempt.status == AttemptStatus.SUBMITTED))
        ).scalar_one()
        stuck = (
            await self.db.execute(
                select(func.count()).select_from(Attempt).where(
                    Attempt.status == AttemptStatus.SUBMITTED, Attempt.grading_attempts >= self.settings.JOB_MAX_ATTEMPTS
                )
            )
        ).scalar_one()
        return {"submitted": int(waiting), "stuck": int(stuck)}

    # ------------------------------------------------------------------ grading

    async def _paper(self, attempt_id: uuid.UUID) -> list[tuple[AttemptQuestion, str, dict[str, Any], dict[str, Any]]]:
        rows = await self.db.execute(
            select(AttemptQuestion, Question.question_type, QuestionVersion.answer_key, QuestionVersion.body)
            .join(QuestionVersion, QuestionVersion.id == AttemptQuestion.question_version_id)
            .join(Question, Question.id == AttemptQuestion.question_id)
            .where(AttemptQuestion.attempt_id == attempt_id)
            .order_by(AttemptQuestion.position)
        )
        return [(aq, qtype, key, body) for aq, qtype, key, body in rows.all()]

    async def grade_attempt(self, public_id: int) -> None:
        """Score everything that can be scored now and queue the rest. Idempotent: a human grade is never redone, and
        running it again (after a crash, or a regrade) reaches the same result."""
        attempt = await self.attempts.get(public_id, lock=True)
        if attempt.status not in (AttemptStatus.SUBMITTED, AttemptStatus.GRADING, AttemptStatus.GRADED):
            return
        test = await self.attempts.test_of(attempt)
        await AnswerStore(self.db).flush(attempt, self.attempts.buffer)  # anything a late save left in Redis
        store = AnswerStore(self.db)
        answers = await store.load(attempt.id)
        codings = {
            row.question_public_id: row
            for row in (await self.db.execute(select(CodingSubmission).where(CodingSubmission.attempt_id == attempt.id))).scalars()
        }
        now = utcnow()
        for aq, qtype_raw, key, _body in await self._paper(attempt.id):
            qtype = QuestionType(qtype_raw)
            answer = answers.get(aq.question_public_id)
            if answer is None:
                answer = AttemptAnswer(attempt_id=attempt.id, question_public_id=aq.question_public_id, revision=0)
                self.db.add(answer)
                answers[aq.question_public_id] = answer
            if answer.grading_status == GradingStatus.MANUAL_GRADED:
                answer.max_marks = aq.marks
                continue
            response = answer.response
            if qtype in AUTO_GRADED_TYPES:
                self._set(answer, grade_objective(qtype, key, response, aq.marks, negative_percent=test.negative_marking_percent), aq.marks, GradingStatus.AUTO_GRADED, now)
            elif response is None:
                self._set(answer, unanswered(), aq.marks, GradingStatus.AUTO_GRADED, now)
            elif qtype in JUDGED_TYPES:
                coding = codings.get(aq.question_public_id)
                if coding is None:
                    coding = self._new_coding(attempt, aq.question_public_id, _body, response)
                    codings[aq.question_public_id] = coding
                self._apply_coding(answer, coding, key, aq.marks, now)
            else:  # subjective, file submission: a person grades it
                self._pending(answer, GradingStatus.PENDING_MANUAL, aq.marks)
        if attempt.status != AttemptStatus.GRADED:  # a regrade of a graded attempt stays graded
            attempt.status = AttemptStatus.GRADING
        await self.db.flush()
        await self.complete_if_ready(attempt, test)

    @staticmethod
    def _set(answer: AttemptAnswer, grade: Grade, max_marks: float, status: GradingStatus, now: Any) -> None:
        answer.marks_awarded = grade.marks
        answer.max_marks = max_marks
        answer.is_correct = grade.is_correct
        answer.grading_status = status
        answer.graded_by = None
        answer.graded_at = now

    @staticmethod
    def _pending(answer: AttemptAnswer, status: GradingStatus, max_marks: float) -> None:
        answer.marks_awarded = None
        answer.max_marks = max_marks
        answer.is_correct = None
        answer.grading_status = status
        answer.graded_at = None

    def _new_coding(self, attempt: Attempt, question_public_id: int, body: dict[str, Any], response: dict[str, Any]) -> CodingSubmission:
        coding = CodingSubmission(
            attempt_id=attempt.id,
            attempt_public_id=attempt.public_id,
            question_public_id=question_public_id,
            user_id=attempt.user_id,
            organization_id=attempt.organization_id,
            problem_id=int(body["problem_id"]),
            language=response["language"],
            source=response["source"],
            reference=coding_reference(attempt.public_id, question_public_id),
            status=CodingStatus.PENDING,
            available_at=utcnow(),
        )
        self.db.add(coding)
        return coding

    def _apply_coding(self, answer: AttemptAnswer, coding: CodingSubmission, key: dict[str, Any], marks: float, now: Any) -> None:
        if coding.status == CodingStatus.JUDGED:
            self._set(answer, grade_judged(key, coding.score, marks), marks, GradingStatus.AUTO_GRADED, now)
            answer.feedback = None
        elif coding.status == CodingStatus.FAILED:
            # It could not be judged automatically: a person decides, so nothing is lost or left hanging.
            self._pending(answer, GradingStatus.PENDING_MANUAL, marks)
            answer.feedback = "This solution could not be judged automatically and needs a manual grade."
        else:
            self._pending(answer, GradingStatus.PENDING_JUDGE, marks)

    # ------------------------------------------------------------------ completion

    async def complete_if_ready(self, attempt: Attempt, test: Test) -> bool:
        """If no answer is waiting any more, total the marks, mark the attempt graded and hand it to the result rules."""
        pending = (
            await self.db.execute(
                select(func.count()).select_from(AttemptAnswer).where(
                    AttemptAnswer.attempt_id == attempt.id, AttemptAnswer.grading_status.in_(_PENDING)
                )
            )
        ).scalar_one()
        if pending:
            attempt.status = AttemptStatus.GRADING if attempt.status != AttemptStatus.GRADED else attempt.status
            await self.db.commit()
            return False

        earned = (
            await self.db.execute(select(func.coalesce(func.sum(AttemptAnswer.marks_awarded), 0.0)).where(AttemptAnswer.attempt_id == attempt.id))
        ).scalar_one()
        possible = (
            await self.db.execute(select(func.coalesce(func.sum(AttemptQuestion.marks), 0.0)).where(AttemptQuestion.attempt_id == attempt.id))
        ).scalar_one()
        attempt.max_score = round_marks(float(possible or 0.0))
        attempt.score = max(0.0, round_marks(float(earned or 0.0)))  # negative marking never takes a score below zero
        attempt.percent = round(100 * attempt.score / attempt.max_score, 2) if attempt.max_score else 0.0
        attempt.plagiarism_flagged = bool(
            (
                await self.db.execute(
                    select(func.count()).select_from(CodingSubmission).where(CodingSubmission.attempt_id == attempt.id, CodingSubmission.flagged.is_(True))
                )
            ).scalar_one()
        )
        first_time = attempt.status != AttemptStatus.GRADED
        attempt.status = AttemptStatus.GRADED
        attempt.graded_at = attempt.graded_at or utcnow()
        if first_time:
            self.db.add(AttemptEvent(attempt_id=attempt.id, event_type="graded", detail={"score": attempt.score, "max_score": attempt.max_score}))
            write_event(
                self.db,
                event_type="attempt.graded",
                aggregate_type="attempt",
                aggregate_id=attempt.id,
                payload={
                    **attempt_event_payload(attempt, test),
                    "score": attempt.score,
                    "max_score": attempt.max_score,
                    "percent": attempt.percent,
                    "pass_mark_percent": test.pass_mark_percent,
                    "plagiarism_flagged": attempt.plagiarism_flagged,
                },
            )
        await self.results.decide(attempt, test)
        await self.db.commit()
        return True

    # ------------------------------------------------------------------ coding verdicts

    async def on_coding_update(self, coding: CodingSubmission) -> None:
        """A coding row changed (verdict arrived, or it was given up on): regrade its answer and try to complete."""
        attempt = await self._attempt_by_id(coding.attempt_id)
        if attempt.status not in (AttemptStatus.GRADING, AttemptStatus.GRADED):
            await self.db.commit()  # not yet graded: grade_attempt will read the coding row itself
            return
        test = await self.attempts.test_of(attempt)
        answer = (
            await self.db.execute(
                select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id, AttemptAnswer.question_public_id == coding.question_public_id)
            )
        ).scalar_one_or_none()
        paper = {aq.question_public_id: (key, aq.marks) for aq, _t, key, _b in await self._paper(attempt.id)}
        if answer is None or answer.grading_status == GradingStatus.MANUAL_GRADED or coding.question_public_id not in paper:
            await self.complete_if_ready(attempt, test)
            return
        key, marks = paper[coding.question_public_id]
        self._apply_coding(answer, coding, key, marks, utcnow())
        await self.db.flush()
        await self.complete_if_ready(attempt, test)

    async def _attempt_by_id(self, attempt_id: uuid.UUID) -> Attempt:
        attempt = (
            await self.db.execute(
                select(Attempt).where(Attempt.id == attempt_id).with_for_update().execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if attempt is None:
            raise NotFoundError("Attempt not found.", code="ATTEMPT_NOT_FOUND")
        return attempt

    # ------------------------------------------------------------------ manual grading

    async def manual_grade(
        self,
        attempt_public_id: int,
        question_public_id: int,
        grader: AccessTokenClaims,
        *,
        marks: float | None,
        rubric_scores: dict[str, float] | None,
        feedback: str | None,
    ) -> AttemptAnswer:
        attempt = await self.attempts.get(attempt_public_id, lock=True)
        test = await self.attempts.test_of(attempt)
        if not can_grade_attempt(grader, attempt_organization_id=attempt.organization_id, test_owner_id=test.organization_id):
            raise NotFoundError("Attempt not found.", code="ATTEMPT_NOT_FOUND")
        if attempt.status not in (AttemptStatus.GRADING, AttemptStatus.GRADED):
            raise ConflictError("This attempt is not ready to be graded.", code="ATTEMPT_NOT_GRADABLE")
        paper = {aq.question_public_id: (aq, qtype, body) for aq, qtype, _k, body in await self._paper(attempt.id)}
        if question_public_id not in paper:
            raise NotFoundError("Question not found.", code="QUESTION_NOT_FOUND")
        aq, qtype_raw, body = paper[question_public_id]
        qtype = QuestionType(qtype_raw)
        answer = (
            await self.db.execute(
                select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id, AttemptAnswer.question_public_id == question_public_id)
            )
        ).scalar_one_or_none()
        if answer is None:
            raise ConflictError("This attempt is not ready to be graded.", code="ATTEMPT_NOT_GRADABLE")

        manual_type = qtype not in AUTO_GRADED_TYPES and qtype not in JUDGED_TYPES
        if not manual_type and not can_manage_exams(grader):
            raise PermissionDeniedError("Only exam managers can override an automatic grade.", code="OVERRIDE_NOT_ALLOWED")
        if not manual_type and not feedback:
            raise ValidationFailedError(details=[{"field": "feedback", "code": "REQUIRED", "message": "Say why an automatic grade is overridden"}])

        rubric = body.get("rubric") or []
        if rubric_scores is not None:
            if not rubric:
                raise ValidationFailedError(details=[{"field": "rubric_scores", "code": "NO_RUBRIC", "message": "This question has no rubric; give marks instead"}])
            unknown = sorted(set(rubric_scores) - {criterion["id"] for criterion in rubric})
            if unknown:
                raise ValidationFailedError(details=[{"field": "rubric_scores", "code": "UNKNOWN_CRITERION", "message": f"Unknown criteria: {', '.join(unknown)}"}])
            limits = {criterion["id"]: criterion["max_marks"] for criterion in rubric}
            over = sorted(name for name, score in rubric_scores.items() if score < 0 or score > limits[name])
            if over:
                raise ValidationFailedError(details=[{"field": "rubric_scores", "code": "OUT_OF_RANGE", "message": f"Scores must be between 0 and the criterion's maximum: {', '.join(over)}"}])
            grade = grade_rubric(rubric, rubric_scores, aq.marks)
            answer.rubric_scores = rubric_scores
        else:
            if marks is None:
                raise ValidationFailedError(details=[{"field": "marks", "code": "REQUIRED", "message": "Give marks or rubric_scores"}])
            if marks < 0 or marks > aq.marks:
                raise ValidationFailedError(details=[{"field": "marks", "code": "OUT_OF_RANGE", "message": f"Marks must be between 0 and {aq.marks}"}])
            fraction = marks / aq.marks if aq.marks else 0.0
            grade = Grade(fraction=fraction, is_correct=fraction >= 1.0, marks=round_marks(marks), answered=True)
            answer.rubric_scores = None
        self._set(answer, grade, aq.marks, GradingStatus.MANUAL_GRADED, utcnow())
        answer.graded_by = grader.user_id
        answer.feedback = feedback
        self.db.add(
            AttemptEvent(
                attempt_id=attempt.id,
                event_type="answer_graded",
                actor_user_id=grader.user_id,
                detail={"question_id": str(question_public_id), "marks": grade.marks},
            )
        )
        await self.db.flush()
        await self.complete_if_ready(attempt, test)
        return answer

    async def regrade(self, attempt_public_id: int, actor: AccessTokenClaims) -> Attempt:
        """Recompute an attempt's grades (human grades are kept) and re-apply the result rules."""
        attempt = await self.attempts.get(attempt_public_id, lock=True)
        if attempt.status not in (AttemptStatus.GRADING, AttemptStatus.GRADED):
            raise ConflictError("Only a submitted attempt can be regraded.", code="ATTEMPT_NOT_GRADABLE")
        self.db.add(AttemptEvent(attempt_id=attempt.id, event_type="regraded", actor_user_id=actor.user_id))
        await self.db.commit()
        await self.grade_attempt(attempt_public_id)
        return await self.attempts.get(attempt_public_id)
