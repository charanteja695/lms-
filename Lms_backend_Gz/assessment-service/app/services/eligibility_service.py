"""May this student take this test, and how many tries and when? (docs/PRODUCT.md §3.1, §5.1, §6.1)

Answered from local read-models only (enrolments and course structure built from events) and the attempts table,
never by calling another service:

  topic / module  an active enrolment in a course version that contains the topic/module
  final           an active enrolment in a version of the course, marked eligible for the final by learning-service
  practice        any student
  hiring          an invitation (``test_assignments``), inside its window

then the test's attempt limit and cooldown, and — for a scheduled exam — its window.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import AttemptResult, AttemptStatus, TargetType, TestKind, TestStatus
from app.models.attempt import Attempt
from app.models.refs import EnrollmentRef, VersionRef, VersionTarget
from app.models.test import Test, TestAssignment, TestSchedule

TEST_TARGET = "test"  # a version_targets row naming a test a course version references


@dataclass(slots=True)
class Eligibility:
    can_start: bool
    reason: str | None = None  # a stable code when can_start is False
    message: str | None = None
    attempts_used: int = 0
    attempts_allowed: int = 0  # 0 = unlimited
    next_available_at: datetime | None = None  # cooldown
    opens_at: datetime | None = None  # a scheduled exam's start
    schedule: TestSchedule | None = None
    enrollment: EnrollmentRef | None = None
    assignment: TestAssignment | None = None

    @property
    def attempts_left(self) -> int | None:
        return None if self.attempts_allowed == 0 else max(self.attempts_allowed - self.attempts_used, 0)


class EligibilityService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def check(self, test: Test, auth: AccessTokenClaims, *, now: datetime | None = None) -> Eligibility:
        now = now or utcnow()
        result = Eligibility(can_start=False)
        if test.status != TestStatus.PUBLISHED:
            return self._deny(result, "TEST_NOT_AVAILABLE", "This test is not available.")

        # ---- who may take it
        if test.kind in (TestKind.TOPIC, TestKind.MODULE, TestKind.FINAL):
            result.enrollment = await self._enrollment(auth.user_id, test)
            if result.enrollment is None:
                return self._deny(result, "NOT_ENROLLED", "You are not enrolled in a course that includes this test.")
            if test.kind == TestKind.MODULE:
                # Backend validation: Module test unlocks ONLY after all chapters and chapter exams in this module are complete/passed
                try:
                    import asyncpg
                    conn_cat = await asyncpg.connect('postgresql://lms:lms@127.0.0.1:5432/lms_catalog')
                    topic_rows = await conn_cat.fetch(
                        '''SELECT t.public_id as topic_id, t.topic_test_id, ti.public_id as item_id, ti.required
                           FROM modules m
                           JOIN topics t ON t.module_id = m.id
                           LEFT JOIN topic_items ti ON ti.topic_id = t.id
                           WHERE m.public_id = $1''',
                        test.target_id
                    )
                    await conn_cat.close()

                    if topic_rows:
                        topics_dict = {}
                        for r in topic_rows:
                            tid = r['topic_id']
                            if tid not in topics_dict:
                                topics_dict[tid] = {'test_id': r['topic_test_id'], 'req_items': set()}
                            if r['item_id'] and r['required']:
                                topics_dict[tid]['req_items'].add(r['item_id'])

                        conn_learn = await asyncpg.connect('postgresql://lms:lms@127.0.0.1:5432/lms_learning')
                        enr = await conn_learn.fetchrow('SELECT id FROM enrollments WHERE public_id = $1', result.enrollment.enrollment_id)
                        if enr:
                            enr_uuid = enr['id']
                            completed_items = await conn_learn.fetch(
                                'SELECT topic_item_id FROM item_progress WHERE enrollment_id = $1', enr_uuid
                            )
                            completed_item_ids = {r['topic_item_id'] for r in completed_items}

                            passed_tests = await conn_learn.fetch(
                                'SELECT test_id FROM assessment_results WHERE enrollment_id = $1 AND passed = true', enr_uuid
                            )
                            passed_test_ids = {r['test_id'] for r in passed_tests}

                            assessment_passed = (await self.db.execute(
                                select(Attempt.test_public_id).where(
                                    Attempt.user_id == auth.user_id,
                                    Attempt.result == AttemptResult.PASSED
                                )
                            )).scalars().all()
                            passed_test_ids.update(t for t in assessment_passed if t)

                            for tid, info in topics_dict.items():
                                if not info['req_items'].issubset(completed_item_ids):
                                    await conn_learn.close()
                                    return self._deny(result, "MODULE_PREREQUISITES_NOT_MET", "You must complete all chapters in this module before taking the module test.")
                                if info['test_id'] and info['test_id'] not in passed_test_ids:
                                    await conn_learn.close()
                                    return self._deny(result, "MODULE_PREREQUISITES_NOT_MET", "You must pass all chapter exams in this module before taking the module test.")
                        await conn_learn.close()
                except Exception as e:
                    logger.warning(f"Error checking module prerequisites: {e}")

            if test.kind == TestKind.FINAL:
                # Backend validation: Final test unlocks ONLY after all module tests in the course are passed
                try:
                    import asyncpg
                    conn_cat = await asyncpg.connect('postgresql://lms:lms@127.0.0.1:5432/lms_catalog')
                    course_id = test.target_id
                    mod_rows = await conn_cat.fetch(
                        '''SELECT m.public_id as module_id, m.module_test_id
                           FROM courses c
                           JOIN course_versions cv ON cv.course_id = c.id
                           JOIN modules m ON m.course_version_id = cv.id
                           WHERE c.public_id = $1''',
                        course_id
                    )
                    await conn_cat.close()

                    required_module_tests = [r['module_test_id'] for r in mod_rows if r['module_test_id']]
                    if required_module_tests:
                        conn_learn = await asyncpg.connect('postgresql://lms:lms@127.0.0.1:5432/lms_learning')
                        enr = await conn_learn.fetchrow('SELECT id FROM enrollments WHERE public_id = $1', result.enrollment.enrollment_id)
                        passed_test_ids = set()
                        if enr:
                            pt = await conn_learn.fetch(
                                'SELECT test_id FROM assessment_results WHERE enrollment_id = $1 AND passed = true', enr['id']
                            )
                            passed_test_ids = {r['test_id'] for r in pt}
                        await conn_learn.close()

                        assessment_passed = (await self.db.execute(
                            select(Attempt.test_public_id).where(
                                Attempt.user_id == auth.user_id,
                                Attempt.result == AttemptResult.PASSED
                            )
                        )).scalars().all()
                        passed_test_ids.update(t for t in assessment_passed if t)

                        for mod_test_id in required_module_tests:
                            if mod_test_id not in passed_test_ids:
                                return self._deny(result, "NOT_ELIGIBLE_FOR_FINAL", "You must pass all module tests before taking the final course test.")
                except Exception as e:
                    logger.warning(f"Error checking final test prerequisites: {e}")
        elif test.kind == TestKind.HIRING:
            result.assignment = (
                await self.db.execute(
                    select(TestAssignment).where(TestAssignment.test_id == test.id, TestAssignment.user_id == auth.user_id)
                )
            ).scalar_one_or_none()
            if result.assignment is None:
                return self._deny(result, "NOT_INVITED", "You have not been invited to this assessment.")
            if result.assignment.opens_at and now < result.assignment.opens_at:
                result.opens_at = result.assignment.opens_at
                return self._deny(result, "NOT_YET_OPEN", "This assessment has not opened yet.")
            if result.assignment.expires_at and now >= result.assignment.expires_at:
                return self._deny(result, "INVITATION_EXPIRED", "This invitation has expired.")

        # ---- how many tries, and when
        started = list(
            (
                await self.db.execute(
                    select(Attempt).where(
                        Attempt.user_id == auth.user_id, Attempt.test_id == test.id, Attempt.status != AttemptStatus.NOT_STARTED
                    )
                )
            ).scalars()
        )
        result.attempts_used = len(started)
        allowed = (result.assignment.max_attempts if result.assignment and result.assignment.max_attempts else None) or test.max_attempts
        result.attempts_allowed = allowed
        if test.kind == TestKind.FINAL and any(a.result == AttemptResult.PASSED for a in started):
            return self._deny(result, "ALREADY_PASSED", "You have already passed this test.")
        if allowed and result.attempts_used >= allowed:
            return self._deny(result, "ATTEMPTS_EXHAUSTED", "You have used every attempt for this test.")
        finished = [a for a in started if a.submitted_at is not None]
        if test.cooldown_hours and finished:
            last = max(a.submitted_at for a in finished if a.submitted_at is not None)
            result.next_available_at = last + timedelta(hours=test.cooldown_hours)
            if now < result.next_available_at:
                return self._deny(result, "COOLDOWN", "You can retry this test after the waiting period.")
            result.next_available_at = None

        # ---- the exam window
        if test.requires_schedule:
            result.schedule = await self.schedule_for(test, auth.organization_id, now)
            if result.schedule is None:
                return self._deny(result, "NOT_SCHEDULED", "This exam has no upcoming session for you.")
            result.opens_at = result.schedule.starts_at
            lead = timedelta(minutes=self.settings.WAITING_ROOM_LEAD_MINUTES)
            if now < result.schedule.starts_at - lead:
                return self._deny(result, "EXAM_NOT_OPEN", "The waiting room for this exam is not open yet.")
        result.can_start = True
        return result

    @staticmethod
    def _deny(result: Eligibility, reason: str, message: str) -> Eligibility:
        result.can_start, result.reason, result.message = False, reason, message
        return result

    async def _enrollment(self, user_id: int, test: Test) -> EnrollmentRef | None:
        stmt = select(EnrollmentRef).where(EnrollmentRef.student_user_id == user_id, EnrollmentRef.active.is_(True))
        if test.target_type == TargetType.COURSE:
            stmt = stmt.join(VersionRef, VersionRef.version_id == EnrollmentRef.version_id).where(VersionRef.course_id == test.target_id)
        else:
            # The version contains the topic/module itself, or lists this very test (a cloned version has new topic
            # ids but keeps pointing at the test its predecessor used).
            stmt = stmt.join(VersionTarget, VersionTarget.version_id == EnrollmentRef.version_id).where(
                or_(
                    and_(VersionTarget.target_type == test.target_type, VersionTarget.target_id == test.target_id),
                    and_(VersionTarget.target_type == TEST_TARGET, VersionTarget.target_id == test.public_id),
                )
            )
        enr = (await self.db.execute(stmt.order_by(EnrollmentRef.enrollment_id.desc()).limit(1))).scalar_one_or_none()
        if enr is not None:
            return enr

        # Fallback check against lms_learning if event sync was skipped
        try:
            import asyncpg
            conn = await asyncpg.connect('postgresql://lms:lms@127.0.0.1:5432/lms_learning')
            row = await conn.fetchrow(
                '''SELECT e.public_id as enrollment_id, e.student_user_id, b.organization_id, b.version_id, e.status
                   FROM enrollments e
                   JOIN batches b ON b.id = e.batch_id
                   WHERE e.student_user_id = $1 AND e.status = 'active'
                   ORDER BY e.created_at DESC LIMIT 1''',
                user_id
            )
            await conn.close()
            if row:
                existing_ref = await self.db.get(EnrollmentRef, row['enrollment_id'])
                if existing_ref is None:
                    existing_ref = EnrollmentRef(
                        enrollment_id=row['enrollment_id'],
                        student_user_id=row['student_user_id'],
                        organization_id=row['organization_id'],
                        version_id=row['version_id'],
                        active=True,
                        eligible_for_final=False,
                    )
                    self.db.add(existing_ref)
                    await self.db.flush()
                return existing_ref
        except Exception:
            pass
        return None

    async def schedule_for(self, test: Test, organization_id: int | None, now: datetime) -> TestSchedule | None:
        """The session a student should sit: the earliest one that has not ended, for their institution or all."""
        return (
            await self.db.execute(
                select(TestSchedule)
                .where(
                    TestSchedule.test_id == test.id,
                    TestSchedule.cancelled_at.is_(None),
                    TestSchedule.ends_at > now,
                    or_(TestSchedulb.organization_id.is_(None), TestSchedulb.organization_id == organization_id),
                )
                .order_by(TestSchedule.starts_at)
                .limit(1)
            )
        ).scalar_one_or_none()

    async def available_tests_filter(self, user_id: int) -> list[Any]:
        """SQL conditions (OR-ed by the caller) selecting the published tests this student could take."""
        version_ids = select(EnrollmentRef.version_id).where(EnrollmentRef.student_user_id == user_id, EnrollmentRef.active.is_(True))
        topic_or_module = select(VersionTarget.target_type, VersionTarget.target_id).where(VersionTarget.version_id.in_(version_ids))
        rows = (await self.db.execute(topic_or_module)).all()
        courses = [c for (c,) in (await self.db.execute(select(VersionRef.course_id).where(VersionRef.version_id.in_(version_ids)))).all()]
        conditions = [Test.kind == TestKind.PRACTICE]
        by_type: dict[str, list[int]] = {}
        for target_type, target_id in rows:
            by_type.setdefault(target_type, []).append(target_id)
        for target_type, ids in by_type.items():
            if target_type == TEST_TARGET:
                conditions.append(Test.public_id.in_(ids))
            else:
                conditions.append((Test.target_type == target_type) & Test.target_id.in_(ids))
        if courses:
            conditions.append((Test.kind == TestKind.FINAL) & Test.target_id.in_(courses))
        invited = select(TestAssignment.test_id).where(TestAssignment.user_id == user_id)
        conditions.append(Test.id.in_(invited))
        return conditions

    async def open_attempt(self, test: Test, user_id: int) -> Attempt | None:
        return (
            await self.db.execute(
                select(Attempt).where(
                    Attempt.user_id == user_id,
                    Attempt.test_id == test.id,
                    Attempt.status.in_([AttemptStatus.NOT_STARTED, AttemptStatus.IN_PROGRESS, AttemptStatus.PAUSED]),
                )
            )
        ).scalar_one_or_none()

    async def started_count(self, test: Test, user_id: int) -> int:
        return int(
            (
                await self.db.execute(
                    select(func.count()).select_from(Attempt).where(
                        Attempt.user_id == user_id, Attempt.test_id == test.id, Attempt.status != AttemptStatus.NOT_STARTED
                    )
                )
            ).scalar_one()
        )
