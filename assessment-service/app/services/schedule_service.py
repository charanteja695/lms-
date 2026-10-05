"""Exam windows and hiring-assessment invitations."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import TestKind, TestStatus
from app.models.test import Test, TestAssignment, TestSchedule
from app.permissions.policy import can_manage_owned_by
from app.schemas.test import AssignmentCreate, ScheduleCreate, ScheduleUpdate


class ScheduleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, public_id: int, test: Test) -> TestSchedule:
        schedule = (
            await self.db.execute(select(TestSchedule).where(TestSchedule.public_id == public_id, TestSchedule.test_id == test.id))
        ).scalar_one_or_none()
        if schedule is None:
            raise NotFoundError("Schedule not found.", code="SCHEDULE_NOT_FOUND")
        return schedule

    async def list_for(self, test: Test) -> list[TestSchedule]:
        rows = await self.db.execute(select(TestSchedule).where(TestSchedule.test_id == test.id).order_by(TestSchedule.starts_at))
        return list(rows.scalars())

    async def create(self, test: Test, data: ScheduleCreate, auth: AccessTokenClaims) -> TestSchedule:
        self._require_manager(test, auth)
        if test.status != TestStatus.PUBLISHED:
            raise ConflictError("Only a published test can be scheduled.", code="TEST_NOT_PUBLISHED")
        schedule = TestSchedule(
            public_id=new_public_id(),
            test_id=test.id,
            title=data.title,
            organization_id=data.organization_id,
            starts_at=data.starts_at,
            ends_at=data.ends_at,
            enforce_end=data.enforce_end,
            results_release_at=data.results_release_at,
            created_by=auth.user_id,
        )
        schedule.id = uuid.uuid4()
        self.db.add(schedule)
        await self.db.commit()
        return schedule

    async def update(self, test: Test, schedule: TestSchedule, data: ScheduleUpdate, auth: AccessTokenClaims) -> TestSchedule:
        self._require_manager(test, auth)
        if schedule.cancelled_at is not None:
            raise ConflictError("This schedule was cancelled.", code="SCHEDULE_CANCELLED")
        fields = data.model_dump(exclude_unset=True)
        started = schedule.starts_at <= utcnow()
        if started and ("starts_at" in fields or "enforce_end" in fields):
            raise ConflictError("A session that has started can only be extended or have its release time changed.", code="SCHEDULE_STARTED")
        for name in ("title", "starts_at", "ends_at", "enforce_end", "results_release_at"):
            if name in fields:
                value = fields[name]
                if isinstance(value, datetime) and value.tzinfo is None:
                    raise ValidationFailedError(details=[{"field": name, "code": "INVALID_DATE", "message": "Give times with a timezone"}])
                setattr(schedule, name, value)
        if schedule.ends_at <= schedule.starts_at:
            await self.db.rollback()
            raise ValidationFailedError(details=[{"field": "ends_at", "code": "OUT_OF_RANGE", "message": "ends_at must be after starts_at"}])
        await self.db.commit()
        return schedule

    async def cancel(self, test: Test, schedule: TestSchedule, auth: AccessTokenClaims) -> TestSchedule:
        self._require_manager(test, auth)
        schedule.cancelled_at = schedule.cancelled_at or utcnow()
        await self.db.commit()
        return schedule

    async def invite(self, data: AssignmentCreate, invited_by: int | None = None) -> tuple[TestAssignment, Test]:
        """Invite (or update the invitation of) a candidate to a hiring assessment."""
        test = (await self.db.execute(select(Test).where(Test.public_id == data.test_id))).scalar_one_or_none()
        if test is None or test.kind != TestKind.HIRING:
            raise NotFoundError("Test not found.", code="TEST_NOT_FOUND")
        if test.status != TestStatus.PUBLISHED:
            raise ConflictError("Only a published test can be assigned.", code="TEST_NOT_PUBLISHED")
        for name in ("opens_at", "expires_at"):
            value = getattr(data, name)
            if value is not None and value.tzinfo is None:
                raise ValidationFailedError(details=[{"field": name, "code": "INVALID_DATE", "message": "Give times with a timezone"}])
        if data.opens_at and data.expires_at and data.expires_at <= data.opens_at:
            raise ValidationFailedError(details=[{"field": "expires_at", "code": "OUT_OF_RANGE", "message": "expires_at must be after opens_at"}])
        assignment = (
            await self.db.execute(select(TestAssignment).where(TestAssignment.test_id == test.id, TestAssignment.user_id == data.user_id))
        ).scalar_one_or_none()
        if assignment is None:
            assignment = TestAssignment(test_id=test.id, user_id=data.user_id)
            self.db.add(assignment)
        assignment.reference = data.reference
        assignment.invited_by = invited_by
        assignment.opens_at, assignment.expires_at, assignment.max_attempts = data.opens_at, data.expires_at, data.max_attempts
        await self.db.commit()
        return assignment, test

    @staticmethod
    def _require_manager(test: Test, auth: AccessTokenClaims) -> None:
        if not can_manage_owned_by(auth, test.organization_id):
            raise PermissionDeniedError()
