"""Self-registered learners' bought courses (subscription-service's ``course_access.*`` events).

They study in one batch per course of their organisation ("Individual learners"), marked by ``subscription_id = 0``:
it holds no institution's seats, so no seat is reserved or released for it. Access granted -> an active enrolment
(a returning learner gets a fresh one); access expired -> the enrolment is withdrawn (``enrollment.removed``), exactly
as when a teacher removes a student; buying again re-enrols them. Progress is kept across, keyed by the learner.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_public_id
from app.core.time import utcnow
from app.domain.enums import BatchStatus, EnrollmentStatus
from app.models.batch import Batch
from app.models.course_version_ref import CourseVersionRef
from app.models.enrollment import Enrollment
from app.services.course_structure_service import CourseStructureService
from app.services.institution_ref_service import InstitutionRefService
from app.services.outbox import write_event

LEARNER_BATCH = 0  # Batch.subscription_id of a learner-store batch


class LearnerAccessService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _active_enrollment(self, user_id: int, course_id: int) -> Enrollment | None:
        return (
            await self.db.execute(
                select(Enrollment)
                .join(Batch, Batch.id == Enrollment.batch_id)
                .join(CourseVersionRef, CourseVersionRef.version_id == Batch.version_id)
                .where(
                    Enrollment.student_user_id == user_id, Enrollment.status == EnrollmentStatus.ACTIVE,
                    Batch.subscription_id == LEARNER_BATCH, CourseVersionRef.course_id == course_id,
                )
                .with_for_update(of=Enrollment)
            )
        ).scalars().first()

    async def _learner_batch(self, organization_id: int, course_id: int) -> Batch:
        version = await CourseStructureService(self.db).get_latest_published_for_course(course_id)
        batch = (
            await self.db.execute(
                select(Batch).where(
                    Batch.organization_id == organization_id, Batch.version_id == version.version_id,
                    Batch.subscription_id == LEARNER_BATCH, Batch.status == BatchStatus.ACTIVE,
                )
            )
        ).scalars().first()
        if batch is None:
            await InstitutionRefService(self.db).get_active(organization_id)
            batch = Batch(
                public_id=new_public_id(), organization_id=organization_id, version_id=version.version_id, subscription_id=LEARNER_BATCH,
                name=f"{version.title} · learners"[:200], created_by=0,
            )
            self.db.add(batch)
            await self.db.flush()
        return batch

    async def granted(self, payload: dict[str, Any]) -> None:
        """Access granted or extended: make sure the learner has an active enrolment (idempotent)."""
        user_id, course_id, organization_id = int(payload["user_id"]), int(payload["course_id"]), int(payload["organization_id"])
        if await self._active_enrollment(user_id, course_id) is not None:
            return
        batch = await self._learner_batch(organization_id, course_id)
        enrollment = Enrollment(public_id=new_public_id(), batch_id=batch.id, student_user_id=user_id, enrolled_at=utcnow())
        self.db.add(enrollment)
        await self.db.flush()
        write_event(
            self.db, event_type="enrollment.created", aggregate_id=enrollment.id,
            payload={
                "enrollment_id": str(enrollment.public_id), "batch_id": str(batch.public_id), "student_user_id": str(user_id),
                "organization_id": str(organization_id), "version_id": str(batch.version_id),
            },
        )

    async def expired(self, payload: dict[str, Any]) -> None:
        """Access ended: withdraw the learner's enrolment (idempotent)."""
        enrollment = await self._active_enrollment(int(payload["user_id"]), int(payload["course_id"]))
        if enrollment is None:
            return
        batch = await self.db.get(Batch, enrollment.batch_id)
        enrollment.status, enrollment.withdrawn_at = EnrollmentStatus.WITHDRAWN, utcnow()
        write_event(
            self.db, event_type="enrollment.removed", aggregate_id=enrollment.id,
            payload={
                "enrollment_id": str(enrollment.public_id), "batch_id": str(batch.public_id if batch else ""),
                "student_user_id": str(enrollment.student_user_id), "version_id": str(batch.version_id if batch else ""), "reason": "access_expired",
            },
        )
