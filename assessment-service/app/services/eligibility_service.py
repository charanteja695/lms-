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
            if test.kind == TestKind.FINAL and not result.enrollment.eligible_for_final:
                return self._deny(result, "NOT_ELIGIBLE_FOR_FINAL", "Complete every module before taking the final test.")
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
        return (await self.db.execute(stmt.order_by(EnrollmentRef.enrollment_id.desc()).limit(1))).scalar_one_or_none()

    async def schedule_for(self, test: Test, organization_id: int | None, now: datetime) -> TestSchedule | None:
        """The session a student should sit: the earliest one that has not ended, for their institution or all."""
        return (
            await self.db.execute(
                select(TestSchedule)
                .where(
                    TestSchedule.test_id == test.id,
                    TestSchedule.cancelled_at.is_(None),
                    TestSchedule.ends_at > now,
                    or_(TestSchedule.organization_id.is_(None), TestSchedule.organization_id == organization_id),
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
