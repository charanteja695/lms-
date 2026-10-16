from lms_common.pagination import paginate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients.subscription_client import release_seat, reserve_seat
from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.db.session import flush_or_conflict
from app.domain.enums import BatchStatus, EnrollmentStatus
from app.models.batch import Batch
from app.models.enrollment import Enrollment
from app.schemas.common import ListQuery
from app.services.outbox import write_event


class EnrollmentService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def enroll(self, batch: Batch, student_user_id: int) -> Enrollment:
        if batch.status != BatchStatus.ACTIVE:
            raise BadRequestError("This batch is archived and cannot accept new enrolments.", code="BATCH_NOT_ACTIVE")

        enrollment_public_id = new_public_id()
        # Captured up front: if the insert below fails, the session rolls back and expires
        # every attribute on `batch`, and refreshing an expired attribute needs an async
        # round trip that can't happen from inside a plain `except` block.
        subscription_id, batch_public_id, organization_id, version_id = (
            batch.subscription_id,
            batch.public_id,
            batch.organization_id,
            batch.version_id,
        )

        # Reserve the seat first: if subscription-service rejects it (no capacity, subscription
        # not active), no enrolment row is ever created. reservation_key is this enrolment's own
        # id, generated up front, so a retried call after a crash is idempotent on their side too.
        await reserve_seat(self.settings, subscription_id, str(enrollment_public_id))

        enrollment = Enrollment(
            public_id=enrollment_public_id,
            batch=batch,  # sets batch_id and populates the relationship for the response schema
            student_user_id=student_user_id,
            enrolled_at=utcnow(),
        )
        self.db.add(enrollment)
        try:
            # One transaction for the enrolment row and its outbox event: either both commit
            # together or neither does (see lms-backend/README.md §5, transactional outbox).
            await flush_or_conflict(self.db, "This student is already enrolled in this batch.")
            write_event(
                self.db,
                event_type="enrollment.created",
                aggregate_id=enrollment.id,
                payload={
                    "enrollment_id": str(enrollment.public_id),
                    "batch_id": str(batch_public_id),
                    "student_user_id": str(student_user_id),
                    "organization_id": str(organization_id),
                    "version_id": str(version_id),
                },
            )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            await release_seat(self.settings, subscription_id, str(enrollment_public_id))
            raise
        return enrollment

    async def withdraw(self, enrollment: Enrollment, batch: Batch) -> Enrollment:
        if enrollment.status != EnrollmentStatus.ACTIVE:
            raise BadRequestError("This enrolment is not active.", code="ENROLLMENT_NOT_ACTIVE")

        enrollment.status = EnrollmentStatus.WITHDRAWN
        enrollment.withdrawn_at = utcnow()
        write_event(
            self.db,
            event_type="enrollment.removed",
            aggregate_id=enrollment.id,
            payload={
                "enrollment_id": str(enrollment.public_id),
                "batch_id": str(batch.public_id),
                "student_user_id": str(enrollment.student_user_id),
                "version_id": str(batch.version_id),
            },
        )
        await self.db.commit()
        await release_seat(self.settings, batch.subscription_id, str(enrollment.public_id))
        return enrollment

    async def get(self, enrollment_id: int) -> Enrollment:
        enrollment = (
            await self.db.execute(
                select(Enrollment).where(Enrollment.public_id == enrollment_id).options(selectinload(Enrollment.batch))
            )
        ).scalar_one_or_none()
        if enrollment is None:
            raise NotFoundError("Enrollment not found.", code="ENROLLMENT_NOT_FOUND")
        return enrollment

    async def is_enrolled(self, batch: Batch, student_user_id: int) -> bool:
        """Whether this student has (or had) an enrolment in the batch: they may read that batch."""
        stmt = select(Enrollment.id).where(Enrollment.batch_id == batch.id, Enrollment.student_user_id == student_user_id).limit(1)
        return (await self.db.execute(stmt)).first() is not None

    async def list_enrollments(
        self, query: ListQuery, *, batch_id: int | None, organization_ids: tuple[int, ...] | None, student_user_id: int | None
    ) -> tuple[list[Enrollment], int, bool]:
        stmt = select(Enrollment)
        if batch_id is not None or organization_ids is not None:
            stmt = stmt.join(Batch, Batch.id == Enrollment.batch_id)
            if batch_id is not None:
                stmt = stmt.where(Batch.public_id == batch_id)
            if organization_ids is not None:
                stmt = stmt.where(Batch.organization_id.in_(organization_ids))
        if student_user_id is not None:
            stmt = stmt.where(Enrollment.student_user_id == student_user_id)
        if query.status:
            stmt = stmt.where(Enrollment.status == query.status)
        stmt = stmt.order_by(Enrollment.created_at.desc() if query.sort_order == "desc" else Enrollment.created_at.asc())
        return await paginate(self.db, stmt, query.page, query.per_page, options=(selectinload(Enrollment.batch),))
