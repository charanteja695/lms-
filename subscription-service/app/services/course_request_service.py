from datetime import timedelta

from lms_common.pagination import paginate
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.db.session import commit_or_conflict
from app.domain.enums import CourseRequestStatus
from app.entitlements.cache import sync_entitlement
from app.models.course_request import CourseRequest
from app.models.subscription import Subscription
from app.schemas.common import ListQuery
from app.schemas.course_request import ApproveRequest, CourseRequestCreate
from app.services.course_ref_service import CourseRefService
from app.services.institution_ref_service import InstitutionRefService
from app.services.outbox import write_event


def _decision_payload(request: CourseRequest) -> dict[str, str]:
    """Who asked for what, so a consumer (notification-service) can tell the requester without calling back."""
    return {
        "course_request_id": str(request.public_id),
        "organization_id": str(request.organization_id),
        "course_id": str(request.course_id),
        "requested_by": str(request.requested_by),
    }


class CourseRequestService:
    def __init__(self, db: AsyncSession, settings: Settings, redis: Redis) -> None:
        self.db = db
        self.settings = settings
        self.redis = redis

    async def submit(self, actor_user_id: int, organization_id: int, data: CourseRequestCreate) -> CourseRequest:
        await InstitutionRefService(self.db).get_active(organization_id)
        await CourseRefService(self.db).get_requestable(data.course_id)

        existing = (
            await self.db.execute(
                select(CourseRequest.id).where(
                    CourseRequest.organization_id == organization_id,
                    CourseRequest.course_id == data.course_id,
                    CourseRequest.status == CourseRequestStatus.SUBMITTED,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError("A request for this course is already pending.", code="REQUEST_ALREADY_PENDING")

        request = CourseRequest(
            public_id=new_public_id(),
            organization_id=organization_id,
            course_id=data.course_id,
            requested_seats=data.requested_seats,
            requested_term_days=data.requested_term_days,
            requested_by=actor_user_id,
        )
        self.db.add(request)
        await commit_or_conflict(self.db)
        write_event(
            self.db,
            event_type="course_request.submitted",
            aggregate_id=request.id,
            payload={
                "course_request_id": str(request.public_id),
                "organization_id": str(organization_id),
                "course_id": str(data.course_id),
            },
        )
        await self.db.commit()
        return request

    async def get(self, course_request_id: int) -> CourseRequest:
        request = (
            await self.db.execute(select(CourseRequest).where(CourseRequest.public_id == course_request_id))
        ).scalar_one_or_none()
        if request is None:
            raise NotFoundError("Course request not found.", code="COURSE_REQUEST_NOT_FOUND")
        return request

    async def list_requests(self, query: ListQuery, *, organization_id: int | None) -> tuple[list[CourseRequest], int, bool]:
        stmt = select(CourseRequest)
        if organization_id is not None:
            stmt = stmt.where(CourseRequest.organization_id == organization_id)
        if query.status:
            stmt = stmt.where(CourseRequest.status == query.status)
        stmt = stmt.order_by(
            CourseRequest.created_at.desc() if query.sort_order == "desc" else CourseRequest.created_at.asc()
        )
        return await paginate(self.db, stmt, query.page, query.per_page)

    async def approve(self, actor_user_id: int, request: CourseRequest, data: ApproveRequest) -> Subscription:
        if request.status != CourseRequestStatus.SUBMITTED:
            raise BadRequestError("Only a pending request can be approved.", code="REQUEST_NOT_PENDING")

        seats = data.seats or request.requested_seats
        term_days = data.term_days or request.requested_term_days
        now = utcnow()

        subscription = Subscription(
            public_id=new_public_id(),
            organization_id=request.organization_id,
            course_id=request.course_id,
            course_request_id=request.id,
            seats_total=seats,
            starts_at=now,
            ends_at=now + timedelta(days=term_days),
            created_by=actor_user_id,
        )
        self.db.add(subscription)

        request.status = CourseRequestStatus.APPROVED
        request.decided_by = actor_user_id
        request.decided_at = now

        write_event(
            self.db,
            event_type="course_request.decided",
            aggregate_id=request.id,
            payload={**_decision_payload(request), "decision": "approved"},
        )
        await self.db.flush()
        write_event(
            self.db,
            event_type="subscription.activated",
            aggregate_id=subscription.id,
            payload={
                "subscription_id": str(subscription.public_id),
                "organization_id": str(subscription.organization_id),
                "course_id": str(subscription.course_id),
                "seats_total": subscription.seats_total,
                "ends_at": subscription.ends_at.isoformat(),
            },
        )
        await commit_or_conflict(self.db, "This institution already has an active subscription to this course.")
        await sync_entitlement(self.redis, key_prefix=self.settings.ENTITLEMENT_KEY_PREFIX, subscription=subscription)
        return subscription

    async def reject(self, actor_user_id: int, request: CourseRequest, reason: str) -> CourseRequest:
        if request.status != CourseRequestStatus.SUBMITTED:
            raise BadRequestError("Only a pending request can be rejected.", code="REQUEST_NOT_PENDING")

        request.status = CourseRequestStatus.REJECTED
        request.decided_by = actor_user_id
        request.decided_at = utcnow()
        request.decision_reason = reason
        write_event(
            self.db,
            event_type="course_request.decided",
            aggregate_id=request.id,
            payload={**_decision_payload(request), "decision": "rejected", "reason": reason},
        )
        await self.db.commit()
        return request
