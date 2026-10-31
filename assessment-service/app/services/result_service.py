"""From a graded attempt to a result (docs/PRODUCT.md §3.1, §5.1, §5.3).

  Pass = score >= the test's pass mark AND proctoring integrity is not_required, clear or reviewed_ok.

A score below the pass mark fails at once; a passing score on a proctored test waits for the integrity decision
(proctoring-service's ``integrity.decided``); an ``invalidated`` decision always wins. Nothing here ever decides an
integrity case: a human confirms every invalidation, in proctoring-service.

A decided result becomes official when it is *released* — immediately, when the exam window closes, or when staff
release it (``result_visibility``). Release is what a student sees and what the rest of the platform hears
(``attempt.finalized``, and for a final test ``course.passed`` / ``course.failed`` / ``course.pass_revoked``).
"""

import logging
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.time import utcnow
from app.domain.enums import (
    INTEGRITY_PASSING,
    AttemptResult,
    AttemptStatus,
    IntegrityStatus,
    ResultVisibility,
    TestKind,
)
from app.models.attempt import Attempt, AttemptEvent
from app.models.test import Test, TestSchedule
from app.services.attempt_service import attempt_event_payload
from app.services.outbox import write_event

logger = logging.getLogger(__name__)

STATS_DIRTY_SET = "assessment:stats:dirty"
_DECISIONS = {
    "clear": IntegrityStatus.CLEAR,
    "reviewed_ok": IntegrityStatus.REVIEWED_OK,
    "invalidated": IntegrityStatus.INVALIDATED,
}


def _iso(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class ResultService:
    def __init__(self, db: AsyncSession, settings: Settings, redis: Redis | None = None) -> None:
        self.db = db
        self.settings = settings
        self.redis = redis

    # ------------------------------------------------------------------ the decision

    async def decide(self, attempt: Attempt, test: Test) -> None:
        """Apply the pass rule to a graded attempt. Does not commit. Idempotent: calling it again with nothing
        changed does nothing, and a changed outcome after release is announced again with a higher revision."""
        prior = attempt.result
        passed_score = (attempt.percent or 0.0) >= test.pass_mark_percent
        if attempt.integrity_status == IntegrityStatus.INVALIDATED:
            result = AttemptResult.INVALIDATED
        elif not passed_score:
            result = AttemptResult.FAILED
        elif attempt.integrity_status in INTEGRITY_PASSING:
            result = AttemptResult.PASSED
        else:
            result = AttemptResult.PENDING  # a passing score waiting for the integrity decision
        attempt.result = result
        if result == AttemptResult.PENDING:
            return
        if prior == result and attempt.finalized_at is not None:
            return
        now = utcnow()
        attempt.finalized_at = attempt.finalized_at or now
        if attempt.results_visible_at is not None:  # already official: the change is announced straight away
            await self.release(attempt, test, previous_result=prior)
            return
        due = await self._release_time(attempt, test, now)
        if due is not None and due <= now:
            await self.release(attempt, test)
        else:
            attempt.release_due_at = due  # None: staff release it

    async def _release_time(self, attempt: Attempt, test: Test, now: datetime) -> datetime | None:
        if test.result_visibility == ResultVisibility.MANUAL:
            return None
        if test.result_visibility == ResultVisibility.AFTER_WINDOW and attempt.schedule_id is not None:
            schedule = await self.db.get(TestSchedule, attempt.schedule_id)
            if schedule is not None:
                return schedule.results_release_at or schedule.ends_at
        return now

    # ------------------------------------------------------------------ release

    async def release(self, attempt: Attempt, test: Test, *, previous_result: str | None = None) -> None:
        """Make the result official: visible to the student, and announced to the platform. Does not commit."""
        now = utcnow()
        attempt.results_visible_at = attempt.results_visible_at or now
        attempt.finalize_revision += 1
        base = attempt_event_payload(attempt, test)
        payload: dict[str, Any] = {
            **base,
            "result": attempt.result,
            "previous_result": previous_result,
            "score": attempt.score,
            "max_score": attempt.max_score,
            "percent": attempt.percent,
            "pass_mark_percent": test.pass_mark_percent,
            "integrity_status": attempt.integrity_status,
            "revision": attempt.finalize_revision,
            "finalized_at": _iso(attempt.finalized_at),
            "released_at": _iso(attempt.results_visible_at),
        }
        self.db.add(AttemptEvent(attempt_id=attempt.id, event_type="released", detail={"result": attempt.result, "revision": attempt.finalize_revision}))
        write_event(self.db, event_type="attempt.finalized", aggregate_type="attempt", aggregate_id=attempt.id, payload=payload)
        # Direct sync to learning-service assessment_results
        if test.kind in (TestKind.TOPIC, TestKind.MODULE) and attempt.enrollment_id:
            try:
                import asyncpg, uuid as _uuid
                conn_learn = await asyncpg.connect('postgresql://lms:lms@127.0.0.1:5432/lms_learning')
                enr_uuid = await conn_learn.fetchval('SELECT id FROM enrollments WHERE public_id = $1', attempt.enrollment_id)
                if enr_uuid:
                    passed_bool = (attempt.result == AttemptResult.PASSED)
                    existing_ar = await conn_learn.fetchrow('SELECT id, passed FROM assessment_results WHERE enrollment_id = $1 AND test_id = $2', enr_uuid, test.public_id)
                    if existing_ar is None:
                        await conn_learn.execute(
                            '''INSERT INTO assessment_results (id, enrollment_id, test_id, passed, percent, attempt_id, revision, created_at, updated_at)
                               VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), NOW())''',
                            _uuid.uuid4(), enr_uuid, test.public_id, passed_bool, float(attempt.percent or 0.0), attempt.public_id, attempt.finalize_revision
                        )
                    elif not existing_ar['passed'] or passed_bool:
                        await conn_learn.execute(
                            '''UPDATE assessment_results SET passed = $1, percent = $2, attempt_id = $3, revision = $4, updated_at = NOW()
                               WHERE id = $5''',
                            passed_bool, float(attempt.percent or 0.0), attempt.public_id, attempt.finalize_revision, existing_ar['id']
                        )
                await conn_learn.close()
            except Exception as e:
                logger.warning(f"Failed to sync assessment result to learning-service: {e}")
        if test.kind == TestKind.FINAL:
            await self._course_events(attempt, test, base, previous_result)
        await self._mark_stats_dirty(test.public_id)

    async def _course_events(self, attempt: Attempt, test: Test, base: dict[str, Any], previous_result: str | None) -> None:
        course = {
            "course_id": base["course_id"] or base["target_id"],
            "version_id": base["version_id"],
            "enrollment_id": base["enrollment_id"],
            "student_user_id": base["user_id"],
            "organization_id": base["organization_id"],
            "test_id": base["test_id"],
            "attempt_id": base["attempt_id"],
        }
        if attempt.result == AttemptResult.PASSED:
            best = (
                await self.db.execute(
                    select(func.max(Attempt.percent)).where(
                        Attempt.user_id == attempt.user_id, Attempt.test_id == attempt.test_id, Attempt.result != AttemptResult.INVALIDATED
                    )
                )
            ).scalar_one()
            try:
                import httpx
                course_id = base.get("course_id") or base.get("target_id")
                cert_payload = {
                    "student_user_id": attempt.user_id,
                    "course_id": int(course_id) if course_id else 0,
                    "attempt_id": attempt.public_id,
                    "version_id": attempt.version_id,
                    "enrollment_id": attempt.enrollment_id,
                    "organization_id": attempt.organization_id,
                    "test_id": test.public_id,
                    "score_percent": float(attempt.percent or 0.0),
                    "percent": float(attempt.percent or 0.0),
                    "passed_at": _iso(attempt.results_visible_at),
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post("http://127.0.0.1:8009/api/v1/certificates/issue-from-pass", json=cert_payload)
            except Exception as e:
                logger.warning(f"Failed to trigger certificate issuance: {e}")
            write_event(
                self.db,
                event_type="course.passed",
                aggregate_type="attempt",
                aggregate_id=attempt.id,
                payload={
                    **course,
                    "score": attempt.score,
                    "max_score": attempt.max_score,
                    "percent": attempt.percent,
                    "best_percent": max(float(best or 0.0), attempt.percent or 0.0),
                    "pass_mark_percent": test.pass_mark_percent,
                    "attempt_no": attempt.attempt_no,
                    "passed_at": _iso(attempt.results_visible_at),
                },
            )
        elif attempt.result == AttemptResult.INVALIDATED and previous_result == AttemptResult.PASSED:
            write_event(
                self.db,
                event_type="course.pass_revoked",
                aggregate_type="attempt",
                aggregate_id=attempt.id,
                payload={**course, "reason": "integrity", "revoked_at": _iso(utcnow())},
            )
        elif attempt.result in (AttemptResult.FAILED, AttemptResult.INVALIDATED) and await self._attempts_exhausted(attempt, test):
            write_event(
                self.db,
                event_type="course.failed",
                aggregate_type="attempt",
                aggregate_id=attempt.id,
                payload={**course, "attempts_used": test.max_attempts, "percent": attempt.percent, "best_percent": await self._best(attempt)},
            )

    async def _best(self, attempt: Attempt) -> float:
        best = (
            await self.db.execute(
                select(func.max(Attempt.percent)).where(
                    Attempt.user_id == attempt.user_id, Attempt.test_id == attempt.test_id, Attempt.result != AttemptResult.INVALIDATED
                )
            )
        ).scalar_one()
        return float(best or 0.0)

    async def _attempts_exhausted(self, attempt: Attempt, test: Test) -> bool:
        """Every attempt is used, none passed and none is still open: the student can no longer pass the course."""
        if not test.max_attempts:
            return False
        rows = (
            await self.db.execute(
                select(Attempt.status, Attempt.result).where(Attempt.user_id == attempt.user_id, Attempt.test_id == attempt.test_id)
            )
        ).all()
        started = [row for row in rows if row[0] != AttemptStatus.NOT_STARTED]
        any_open = any(status in (AttemptStatus.NOT_STARTED, AttemptStatus.IN_PROGRESS, AttemptStatus.PAUSED) for status, _ in rows)
        return len(started) >= test.max_attempts and not any_open and all(result != AttemptResult.PASSED for _, result in started)

    async def release_due(self, limit: int) -> int:
        """Release results whose time has come (the end of an exam window, or staff pressing release)."""
        now = utcnow()
        due = (
            await self.db.execute(
                select(Attempt)
                .where(
                    Attempt.results_visible_at.is_(None),
                    Attempt.release_due_at.is_not(None),
                    Attempt.release_due_at <= now,
                    Attempt.result != AttemptResult.PENDING,
                )
                .order_by(Attempt.release_due_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
        for attempt in due:
            test = (await self.db.execute(select(Test).where(Test.id == attempt.test_id))).scalar_one()
            await self.release(attempt, test)
        await self.db.commit()
        return len(due)

    async def release_test(self, test: Test) -> int:
        """Staff release: every decided, unreleased attempt of the test becomes due now (the worker publishes them
        in batches, so releasing a large exam is one cheap statement)."""
        result = await self.db.execute(
            update(Attempt)
            .where(
                Attempt.test_id == test.id,
                Attempt.results_visible_at.is_(None),
                Attempt.result != AttemptResult.PENDING,
                Attempt.finalized_at.is_not(None),
            )
            .values(release_due_at=utcnow())
        )
        await self.db.commit()
        return int(getattr(result, "rowcount", 0) or 0)

    async def _mark_stats_dirty(self, test_public_id: int) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.sadd(STATS_DIRTY_SET, str(test_public_id))  # type: ignore[misc]
        except RedisError:
            logger.warning("Could not mark test %s for statistics", test_public_id)

    # ------------------------------------------------------------------ integrity (from proctoring-service)

    async def _attempt(self, public_id: int) -> Attempt | None:
        stmt = select(Attempt).where(Attempt.public_id == public_id).with_for_update().execution_options(populate_existing=True)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def integrity_flagged(self, attempt_public_id: int, *, under_review: bool = False) -> None:
        attempt = await self._attempt(attempt_public_id)
        if attempt is None or attempt.integrity_status in (IntegrityStatus.CLEAR, IntegrityStatus.REVIEWED_OK, IntegrityStatus.INVALIDATED):
            return
        attempt.integrity_status = IntegrityStatus.UNDER_REVIEW if under_review else IntegrityStatus.FLAGGED
        self.db.add(AttemptEvent(attempt_id=attempt.id, event_type="integrity_flagged", detail={"status": attempt.integrity_status}))
        await self.db.commit()

    async def integrity_decided(self, attempt_public_id: int, decision: str) -> None:
        """proctoring-service's decision (automatic clear, or a human's reviewed_ok / invalidated). Applied at once if
        the attempt is already graded, otherwise when grading finishes."""
        status = _DECISIONS.get(decision)
        attempt = await self._attempt(attempt_public_id)
        if status is None or attempt is None:
            logger.warning("Ignoring integrity decision %r for attempt %s", decision, attempt_public_id)
            return
        attempt.integrity_status = status
        attempt.integrity_decided_at = utcnow()
        self.db.add(AttemptEvent(attempt_id=attempt.id, event_type="integrity_decided", detail={"decision": decision}))
        if attempt.status == AttemptStatus.GRADED:
            test = (await self.db.execute(select(Test).where(Test.id == attempt.test_id))).scalar_one()
            await self.decide(attempt, test)
        await self.db.commit()
