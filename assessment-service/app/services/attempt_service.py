"""The attempt lifecycle (docs/PRODUCT.md §5.1):

    not_started --start--> in_progress <--pause/unpause--> paused
                               |  submit (manual | timeout | terminated)
                               v
                           submitted --grader--> grading --> graded          (see grading_service)

The server clock is the authority: the deadline is fixed when the attempt starts, every read and write re-checks it,
and the worker sweeps attempts nobody is touching. A student may resume a running attempt after a refresh or crash,
and each resume is logged.
"""

import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.context import RequestContext
from app.core.exceptions import AppError, ConflictError, NotFoundError, PermissionDeniedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import AttemptStatus, IdempotentScope, IntegrityStatus, ProctoringLevel, SubmitReason, TimeMode
from app.models.attempt import Attempt, AttemptEvent, AttemptQuestion, AttemptSection
from app.models.question import Question, QuestionVersion
from app.models.refs import VersionRef
from app.models.test import Test, TestSection
from app.paper.generator import PaperGenerator, PlannedQuestion
from app.paper.render import render_question
from app.services import clock, waiting_room
from app.services.answer_buffer import AnswerBuffer
from app.services.answer_store import AnswerStore
from app.services.attempt_cache import AttemptCache, AttemptMeta
from app.services.clock import SectionClock
from app.services.eligibility_service import Eligibility, EligibilityService
from app.services.idempotency_service import IdempotencyService, request_hash
from app.services.outbox import write_event

logger = logging.getLogger(__name__)

OPEN_STATUSES = (AttemptStatus.NOT_STARTED, AttemptStatus.IN_PROGRESS, AttemptStatus.PAUSED)
_DENIED_AS_FORBIDDEN = {"NOT_ENROLLED", "NOT_ELIGIBLE_FOR_FINAL", "NOT_INVITED", "MODULE_PREREQUISITES_NOT_MET"}


def attempt_event_payload(attempt: Attempt, test: Test) -> dict[str, Any]:
    """The fields every attempt event shares; each event adds its own."""
    return {
        "attempt_id": str(attempt.public_id),
        "test_id": str(test.public_id),
        "test_kind": test.kind,
        "target_type": test.target_type,
        "target_id": str(test.target_id) if test.target_id else None,
        "user_id": str(attempt.user_id),
        "organization_id": str(attempt.organization_id) if attempt.organization_id else None,
        "enrollment_id": str(attempt.enrollment_id) if attempt.enrollment_id else None,
        "version_id": str(attempt.version_id) if attempt.version_id else None,
        "course_id": str(attempt.course_id) if attempt.course_id else None,
        "attempt_no": attempt.attempt_no,
        "proctoring_level": test.proctoring_level,
    }


def _iso(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class AttemptService:
    def __init__(self, db: AsyncSession, settings: Settings, redis: Redis | None = None) -> None:
        self.db = db
        self.settings = settings
        self.redis = redis
        self.cache = AttemptCache(redis, settings)
        self.buffer = AnswerBuffer(redis, settings)
        self.eligibility = EligibilityService(db, settings)

    # ------------------------------------------------------------------ loading

    async def get(self, public_id: int, *, lock: bool = False) -> Attempt:
        stmt = select(Attempt).where(Attempt.public_id == public_id).options(selectinload(Attempt.sections))
        if lock:
            # populate_existing: the caller may already hold this row from an unlocked read, and a lock is worth
            # nothing if the state that is then checked is the stale copy from before the lock was granted.
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        attempt = (await self.db.execute(stmt)).scalar_one_or_none()
        if attempt is None:
            raise NotFoundError("Attempt not found.", code="ATTEMPT_NOT_FOUND")
        return attempt

    async def get_owned(self, public_id: int, user_id: int, *, lock: bool = False) -> Attempt:
        attempt = await self.get(public_id, lock=lock)
        if attempt.user_id != user_id:
            raise NotFoundError("Attempt not found.", code="ATTEMPT_NOT_FOUND")
        return attempt

    async def test_of(self, attempt: Attempt, *, with_sections: bool = False) -> Test:
        stmt = select(Test).where(Test.id == attempt.test_id)
        if with_sections:
            stmt = stmt.options(selectinload(Test.sections))
        return (await self.db.execute(stmt)).scalar_one()

    # ------------------------------------------------------------------ prepare (the waiting room)

    async def prepare(
        self, test: Test, auth: AccessTokenClaims, ctx: RequestContext, *, key: str | None = None
    ) -> Attempt:
        """Prepare a paper for the student, or return the attempt they already have open. The clock does not run and
        no attempt is used up until ``start``."""
        existing = await self.eligibility.open_attempt(test, auth.user_id)
        if existing is not None:
            attempt = await self.refresh(await self.get(existing.public_id))
            if attempt.status in OPEN_STATUSES:
                return attempt

        idempotency = IdempotencyService(self.db)
        payload_hash = request_hash({"test": test.public_id})
        if key:
            remembered = await idempotency.find(auth.user_id, IdempotentScope.ATTEMPT, key, payload_hash)
            if remembered is not None:
                return await self.get(remembered)

        eligibility = await self.eligibility.check(test, auth)
        if not eligibility.can_start:
            raise self._denied(eligibility)

        seed = secrets.randbits(62)
        planned = await PaperGenerator(self.db, self.redis, self.settings).generate(test, seed)
        attempt = Attempt(
            public_id=new_public_id(),
            test_id=test.id,
            test_public_id=test.public_id,
            user_id=auth.user_id,
            organization_id=auth.organization_id,
            attempt_no=0,
            status=AttemptStatus.NOT_STARTED,
            seed=seed,
            schedule_id=eligibility.schedule.id if eligibility.schedule else None,
            client_ip=ctx.ip_address,
            user_agent=ctx.user_agent,
        )
        attempt.id = uuid.uuid4()
        if eligibility.enrollment is not None:
            attempt.enrollment_id = eligibility.enrollment.enrollment_id
            attempt.version_id = eligibility.enrollment.version_id
            attempt.course_id = (
                await self.db.execute(select(VersionRef.course_id).where(VersionRef.version_id == attempt.version_id))
            ).scalar_one_or_none()
        self.db.add(attempt)
        try:
            await self.db.flush()
        except IntegrityError:  # a concurrent prepare for this student and test won: use theirs
            await self.db.rollback()
            winner = await self.eligibility.open_attempt(test, auth.user_id)
            if winner is None:
                raise
            return await self.get(winner.public_id)
        self._add_paper_rows(attempt, test, planned)
        if key:
            idempotency.remember(auth.user_id, IdempotentScope.ATTEMPT, key, payload_hash, attempt.public_id)
        self.db.add(AttemptEvent(attempt_id=attempt.id, event_type="prepared", actor_user_id=auth.user_id, ip_address=ctx.ip_address))
        await self.db.commit()
        await self.cache.put_paper(attempt.public_id, await self._render_paper(attempt.id))
        return await self.get(attempt.public_id)

    def _add_paper_rows(self, attempt: Attempt, test: Test, planned: list[PlannedQuestion]) -> None:
        for position, item in enumerate(planned, start=1):
            self.db.add(
                AttemptQuestion(
                    attempt_id=attempt.id,
                    position=position,
                    section_id=item.section.id,
                    section_position=item.section.position,
                    question_id=item.question.id,
                    question_public_id=item.question.public_id,
                    question_version_id=item.version.id,
                    marks=item.marks,
                    option_order=item.option_order,
                )
            )
        if test.time_mode == TimeMode.PER_SECTION:
            for section in test.sections:
                self.db.add(AttemptSection(attempt_id=attempt.id, section_id=section.id, position=section.position))

    def _denied(self, eligibility: Eligibility) -> AppError:
        reason, message = eligibility.reason or "NOT_ALLOWED", eligibility.message or "You cannot take this test now."
        if reason in _DENIED_AS_FORBIDDEN:
            return PermissionDeniedError(message, code=reason)
        if reason == "TEST_NOT_AVAILABLE":
            return NotFoundError(message, code="TEST_NOT_FOUND")
        details: list[dict[str, Any]] = []
        for name, value in (("next_available_at", eligibility.next_available_at), ("opens_at", eligibility.opens_at)):
            if value is not None and reason in {"COOLDOWN", "EXAM_NOT_OPEN", "NOT_YET_OPEN"}:
                details.append({"field": name, "code": reason, "message": _iso(value)})
        return ConflictError(message, code=reason, details=details)

    # ------------------------------------------------------------------ paper

    async def _render_paper(self, attempt_id: uuid.UUID) -> list[dict[str, Any]]:
        """The student view of the paper, without answer keys."""
        rows = await self.db.execute(
            select(AttemptQuestion, QuestionVersion.text, QuestionVersion.body, Question.question_type, TestSection.public_id)
            .join(QuestionVersion, QuestionVersion.id == AttemptQuestion.question_version_id)
            .join(Question, Question.id == AttemptQuestion.question_id)
            .join(TestSection, TestSection.id == AttemptQuestion.section_id)
            .where(AttemptQuestion.attempt_id == attempt_id)
            .order_by(AttemptQuestion.position)
        )
        return [
            render_question(
                question_public_id=aq.question_public_id,
                position=aq.position,
                section_public_id=section_public_id,
                section_position=aq.section_position,
                qtype=qtype,
                text=text,
                marks=aq.marks,
                body=body,
                option_order=aq.option_order,
            )
            for aq, text, body, qtype, section_public_id in rows.all()
        ]

    async def paper(self, public_id: int, attempt_id: uuid.UUID) -> list[dict[str, Any]]:
        """The rendered paper: from Redis when cached, rebuilt from the database (and re-cached) when not."""
        cached = await self.cache.get_paper(public_id)
        if cached is not None:
            return cached
        paper = await self._render_paper(attempt_id)
        await self.cache.put_paper(public_id, paper)
        return paper

    # ------------------------------------------------------------------ start / resume

    async def start(self, attempt: Attempt, auth: AccessTokenClaims, ctx: RequestContext) -> Attempt:
        """Start the clock. Idempotent for an attempt that is already running (that is a resume)."""
        attempt = await self.get_owned(attempt.public_id, auth.user_id, lock=True)
        if attempt.status in (AttemptStatus.IN_PROGRESS, AttemptStatus.PAUSED):
            return await self.resume(attempt, auth, ctx)
        if attempt.status != AttemptStatus.NOT_STARTED:
            raise ConflictError("This attempt has ended.", code="ATTEMPT_ENDED")

        test = await self.test_of(attempt, with_sections=True)
        now = utcnow()
        eligibility = await self.eligibility.check(test, auth, now=now)
        if not eligibility.can_start and eligibility.reason != "EXAM_NOT_OPEN":
            raise self._denied(eligibility)
        await self._require_precheck(test, auth.user_id)
        window_end: datetime | None = None
        if test.requires_schedule:
            schedule = eligibility.schedule
            if schedule is None:
                raise self._denied(eligibility)
            if now < schedule.starts_at:
                raise ConflictError(
                    "The exam has not started yet.",
                    code="EXAM_NOT_OPEN",
                    details=[{"field": "opens_at", "code": "EXAM_NOT_OPEN", "message": _iso(schedule.starts_at)}],
                )
            attempt.schedule_id = schedule.id
            window_end = schedule.ends_at if schedule.enforce_end else None
            await waiting_room.admit(self.redis, self.settings, test.public_id)

        section_limits = [(section.time_limit_minutes or 0) * 60 for section in test.sections]
        deadline = clock.overall_deadline(
            time_mode=test.time_mode,
            duration_minutes=test.duration_minutes,
            section_limits_seconds=section_limits,
            started_at=now,
            window_end=window_end,
        )
        attempt.status = AttemptStatus.IN_PROGRESS
        attempt.attempt_no = eligibility.attempts_used + 1
        attempt.started_at, attempt.deadline_at = now, deadline
        attempt.client_ip, attempt.user_agent = ctx.ip_address, ctx.user_agent
        if test.proctoring_level != ProctoringLevel.NONE:
            attempt.integrity_status = IntegrityStatus.PENDING
        if test.time_mode == TimeMode.PER_SECTION:
            first = attempt.sections[0] if attempt.sections else None
            if first is not None:
                first.started_at = now
                first.deadline_at = min(now + timedelta(seconds=(test.sections[0].time_limit_minutes or 0) * 60), deadline)

        self.db.add(AttemptEvent(attempt_id=attempt.id, event_type="started", actor_user_id=auth.user_id, ip_address=ctx.ip_address))
        write_event(
            self.db,
            event_type="attempt.started",
            aggregate_type="attempt",
            aggregate_id=attempt.id,
            payload={**attempt_event_payload(attempt, test), "started_at": _iso(now), "deadline_at": _iso(deadline)},
        )
        await self.db.commit()
        await self._publish_meta(attempt)
        return attempt

    async def _require_precheck(self, test: Test, user_id: int) -> None:
        """A proctored test starts only after proctoring-service has passed the student's pre-check (consent, system
        check and, for strict tests, identity photos). It publishes a short-lived Redis key; this reads it."""
        if not self.settings.PROCTORING_PRECHECK_REQUIRED or test.proctoring_level == ProctoringLevel.NONE or self.redis is None:
            return
        try:
            ready = await self.redis.exists(f"{self.settings.PROCTORING_READY_KEY_PREFIX}:{user_id}:{test.public_id}")
        except RedisError:
            logger.warning("Could not read the proctoring pre-check flag; allowing the start")
            return
        if not ready:
            raise ConflictError(
                "Complete the proctoring pre-check before starting this test.", code="PROCTORING_PRECHECK_REQUIRED"
            )

    async def resume(self, attempt: Attempt, auth: AccessTokenClaims, ctx: RequestContext) -> Attempt:
        """Re-open a running attempt (after a refresh or a device crash). Every resume is logged."""
        attempt = await self.refresh(await self.get_owned(attempt.public_id, auth.user_id, lock=True))
        if attempt.status == AttemptStatus.NOT_STARTED:
            raise ConflictError("Start the attempt first.", code="ATTEMPT_NOT_STARTED")
        if attempt.status not in (AttemptStatus.IN_PROGRESS, AttemptStatus.PAUSED):
            raise ConflictError("This attempt has ended.", code="ATTEMPT_ENDED")
        attempt.resume_count += 1
        self.db.add(
            AttemptEvent(attempt_id=attempt.id, event_type="resumed", actor_user_id=auth.user_id, ip_address=ctx.ip_address, detail={"resume_count": attempt.resume_count})
        )
        await self.db.commit()
        return attempt

    # ------------------------------------------------------------------ the clock

    def _clocks(self, attempt: Attempt, test_sections: list[TestSection] | None = None) -> list[SectionClock]:
        limits = {section.id: section.time_limit_minutes for section in test_sections or []}
        public = {section.id: section.public_id for section in test_sections or []}
        return [
            SectionClock(
                position=row.position,
                section_id=public.get(row.section_id, 0),
                limit_seconds=(limits.get(row.section_id) or 0) * 60,
                started_at=row.started_at,
                deadline_at=row.deadline_at,
                finished_at=row.finished_at,
            )
            for row in attempt.sections
        ]

    async def refresh(self, attempt: Attempt) -> Attempt:
        """Apply the clock to a running attempt: close sections whose time is up, and submit an attempt past its
        deadline (plus the network grace). Safe to call on every read."""
        if attempt.status != AttemptStatus.IN_PROGRESS or attempt.deadline_at is None:
            return attempt
        now = utcnow()
        if attempt.sections:
            test = await self.test_of(attempt, with_sections=True)
            clocks = self._clocks(attempt, list(test.sections))
            if clock.advance(clocks, now, attempt.deadline_at):
                self._write_clocks(attempt, clocks)
                await self.db.commit()
                await self._publish_meta(attempt)
        if now > attempt.deadline_at + timedelta(seconds=self.settings.ATTEMPT_GRACE_SECONDS):
            return await self.submit(attempt, reason=SubmitReason.TIMEOUT)
        return attempt

    @staticmethod
    def _write_clocks(attempt: Attempt, clocks: list[SectionClock]) -> None:
        by_position = {c.position: c for c in clocks}
        for row in attempt.sections:
            source = by_position[row.position]
            row.started_at, row.deadline_at, row.finished_at = source.started_at, source.deadline_at, source.finished_at

    async def _publish_meta(self, attempt: Attempt) -> None:
        clocks: list[SectionClock] = []
        if attempt.sections:
            test = await self.test_of(attempt, with_sections=True)
            clocks = self._clocks(attempt, list(test.sections))
        await self.cache.put_meta(
            AttemptMeta(
                attempt_id=str(attempt.id),
                public_id=attempt.public_id,
                user_id=attempt.user_id,
                status=attempt.status,
                deadline_at=attempt.deadline_at,
                per_section=bool(attempt.sections),
                sections=clocks,
            )
        )

    async def gate(self, public_id: int, user_id: int) -> AttemptMeta:
        """The hot path's check before accepting an answer: the attempt is the caller's, running, and within its
        time. Answered from the Redis copy when there is one; only a miss or a timeout touches the database."""
        meta = await self.cache.get_meta(public_id)
        if meta is None:
            attempt = await self.refresh(await self.get_owned(public_id, user_id))
            await self._publish_meta(attempt)
            meta = await self.cache.get_meta(public_id) or AttemptMeta(
                attempt_id=str(attempt.id), public_id=public_id, user_id=user_id, status=attempt.status, deadline_at=attempt.deadline_at
            )
        if meta.user_id != user_id:
            raise NotFoundError("Attempt not found.", code="ATTEMPT_NOT_FOUND")
        if meta.status == AttemptStatus.IN_PROGRESS and meta.deadline_at is not None:
            if utcnow() > meta.deadline_at + timedelta(seconds=self.settings.ATTEMPT_GRACE_SECONDS):
                await self.refresh(await self.get_owned(public_id, user_id))  # submits it on timeout
                raise ConflictError("Time is up; your answers have been submitted.", code="ATTEMPT_ENDED")
            return meta
        if meta.status == AttemptStatus.NOT_STARTED:
            raise ConflictError("Start the attempt first.", code="ATTEMPT_NOT_STARTED")
        if meta.status == AttemptStatus.PAUSED:
            raise ConflictError("This attempt is paused.", code="ATTEMPT_PAUSED")
        raise ConflictError("This attempt has ended.", code="ATTEMPT_ENDED")

    async def finish_section(self, attempt: Attempt, auth: AccessTokenClaims) -> Attempt:
        """Per-section tests: the student is done with the section they are in; the next one starts now."""
        attempt = await self.refresh(await self.get_owned(attempt.public_id, auth.user_id, lock=True))
        if attempt.status != AttemptStatus.IN_PROGRESS or attempt.deadline_at is None:
            raise ConflictError("This attempt is not running.", code="ATTEMPT_NOT_RUNNING")
        if not attempt.sections:
            raise ConflictError("This test is timed as a whole; it has no sections to finish.", code="NOT_PER_SECTION")
        test = await self.test_of(attempt, with_sections=True)
        clocks = self._clocks(attempt, list(test.sections))
        finished = clock.finish_current(clocks, utcnow(), attempt.deadline_at)
        if finished is None:
            raise ConflictError("Every section is already finished.", code="NO_OPEN_SECTION")
        self._write_clocks(attempt, clocks)
        self.db.add(AttemptEvent(attempt_id=attempt.id, event_type="section_finished", actor_user_id=auth.user_id, detail={"position": finished.position}))
        await self.db.commit()
        if clock.all_finished(clocks):
            return await self.submit(attempt, reason=SubmitReason.MANUAL, actor_user_id=auth.user_id)
        await self._publish_meta(attempt)
        return attempt

    # ------------------------------------------------------------------ submit / pause / terminate

    async def submit(
        self,
        attempt: Attempt,
        *,
        reason: SubmitReason,
        actor_user_id: int | None = None,
        ip_address: str | None = None,
    ) -> Attempt:
        """End the attempt and queue it for grading. Idempotent: submitting twice is not an error."""
        attempt = await self.get(attempt.public_id, lock=True)
        if attempt.status == AttemptStatus.NOT_STARTED:
            raise ConflictError("Start the attempt first.", code="ATTEMPT_NOT_STARTED")
        if attempt.status not in (AttemptStatus.IN_PROGRESS, AttemptStatus.PAUSED):
            return attempt
        now = utcnow()
        attempt.status = AttemptStatus.SUBMITTED
        attempt.submit_reason = reason
        # A timeout is dated at the deadline, so the cooldown does not run from whenever the sweep noticed.
        attempt.submitted_at = min(now, attempt.deadline_at) if reason == SubmitReason.TIMEOUT and attempt.deadline_at else now
        attempt.grading_available_at = now
        attempt.paused_at = None
        for section in attempt.sections:
            if section.finished_at is None:
                section.finished_at = attempt.submitted_at
        test = await self.test_of(attempt)
        self.db.add(
            AttemptEvent(attempt_id=attempt.id, event_type="submitted", actor_user_id=actor_user_id or attempt.user_id, ip_address=ip_address, detail={"reason": reason})
        )
        write_event(
            self.db,
            event_type="attempt.submitted",
            aggregate_type="attempt",
            aggregate_id=attempt.id,
            payload={**attempt_event_payload(attempt, test), "submitted_at": _iso(attempt.submitted_at), "submit_reason": reason},
        )
        await self.db.commit()
        await self._publish_meta(attempt)  # answers are refused from here on
        await AnswerStore(self.db).flush(attempt, self.buffer)
        return attempt

    async def pause(self, attempt: Attempt, actor_user_id: int, reason: str | None) -> Attempt:
        attempt = await self.refresh(await self.get(attempt.public_id, lock=True))
        if attempt.status != AttemptStatus.IN_PROGRESS:
            raise ConflictError("Only a running attempt can be paused.", code="ATTEMPT_NOT_RUNNING")
        attempt.status = AttemptStatus.PAUSED
        attempt.paused_at = utcnow()
        self.db.add(AttemptEvent(attempt_id=attempt.id, event_type="paused", actor_user_id=actor_user_id, detail={"reason": reason}))
        await self.db.commit()
        await self._publish_meta(attempt)
        return attempt

    async def unpause(self, attempt: Attempt, actor_user_id: int) -> Attempt:
        attempt = await self.get(attempt.public_id, lock=True)
        if attempt.status != AttemptStatus.PAUSED or attempt.paused_at is None or attempt.deadline_at is None:
            raise ConflictError("This attempt is not paused.", code="ATTEMPT_NOT_PAUSED")
        stopped = (utcnow() - attempt.paused_at).total_seconds()
        attempt.deadline_at += timedelta(seconds=stopped)  # the paused time is given back
        if attempt.sections:
            test = await self.test_of(attempt, with_sections=True)
            clocks = self._clocks(attempt, list(test.sections))
            clock.shift(clocks, stopped)
            self._write_clocks(attempt, clocks)
        attempt.status, attempt.paused_at = AttemptStatus.IN_PROGRESS, None
        self.db.add(AttemptEvent(attempt_id=attempt.id, event_type="unpaused", actor_user_id=actor_user_id, detail={"seconds_stopped": round(stopped)}))
        await self.db.commit()
        await self._publish_meta(attempt)
        return attempt

    async def terminate(self, attempt: Attempt, actor_user_id: int, reason: str | None, ip_address: str | None = None) -> Attempt:
        attempt = await self.get(attempt.public_id)
        result = await self.submit(attempt, reason=SubmitReason.TERMINATED, actor_user_id=actor_user_id, ip_address=ip_address)
        self.db.add(AttemptEvent(attempt_id=attempt.id, event_type="terminated", actor_user_id=actor_user_id, detail={"reason": reason}))
        await self.db.commit()
        return result

    # ------------------------------------------------------------------ housekeeping

    async def sweep_timeouts(self, limit: int) -> int:
        """Submit running attempts that are past their deadline (plus grace) and that nobody is touching."""
        cutoff = utcnow() - timedelta(seconds=self.settings.ATTEMPT_GRACE_SECONDS)
        due = (
            await self.db.execute(
                select(Attempt.public_id)
                .where(Attempt.status == AttemptStatus.IN_PROGRESS, Attempt.deadline_at < cutoff)
                .order_by(Attempt.deadline_at)
                .limit(limit)
            )
        ).scalars().all()
        submitted = 0
        for public_id in due:
            try:
                await self.submit(await self.get(public_id), reason=SubmitReason.TIMEOUT)
                submitted += 1
            except Exception:
                await self.db.rollback()
                logger.exception("Could not auto-submit attempt %s", public_id)
        return submitted

    async def drop_stale_prepared(self) -> int:
        """Prepared attempts nobody started free their storage after a while."""
        cutoff = utcnow() - timedelta(hours=self.settings.PREPARED_ATTEMPT_TTL_HOURS)
        stale = select(Attempt.id).where(Attempt.status == AttemptStatus.NOT_STARTED, Attempt.created_at < cutoff)
        result = await self.db.execute(delete(Attempt).where(Attempt.id.in_(stale)))
        await self.db.commit()
        return int(getattr(result, "rowcount", 0) or 0)
