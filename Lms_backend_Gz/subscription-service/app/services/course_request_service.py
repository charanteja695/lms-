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
from app.domain.enums import CourseRequestStatus, SubscriptionStatus
from app.entitlements.cache import sync_entitlement
from app.models.course_ref import CourseRef
from app.models.course_request import CourseRequest
from app.models.institution_ref import InstitutionRef
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

    async def _enrich_requests(self, requests: list[CourseRequest]) -> None:
        if not requests:
            return
        course_ids = {r.course_id for r in requests}
        org_ids = {r.organization_id for r in requests}
        user_ids = {r.requested_by for r in requests}

        course_names: dict[int, str] = {}
        inst_names: dict[int, str] = {}
        user_names: dict[int, str] = {}

        if course_ids:
            c_rows = (await self.db.execute(select(CourseRef).where(CourseRef.course_id.in_(course_ids)))).scalars().all()
            for c in c_rows:
                course_names[c.course_id] = c.title

        if org_ids:
            i_rows = (await self.db.execute(select(InstitutionRef).where(InstitutionRef.organization_id.in_(org_ids)))).scalars().all()
            for i in i_rows:
                inst_names[i.organization_id] = i.name

        missing_courses = course_ids - set(course_names.keys())
        missing_orgs = org_ids - set(inst_names.keys())
        try:
            import asyncpg
            if missing_courses:
                cat_conn = await asyncpg.connect("postgresql://lms:lms@localhost:5432/lms_catalog")
                try:
                    c_rows = await cat_conn.fetch("SELECT public_id, title FROM courses WHERE public_id = ANY($1)", list(missing_courses))
                    for r in c_rows:
                        course_names[r["public_id"]] = r["title"]
                finally:
                    await cat_conn.close()

            um_conn = await asyncpg.connect("postgresql://lms:lms@localhost:5432/lms_user_management")
            try:
                if missing_orgs:
                    i_rows = await um_conn.fetch("SELECT public_id, name FROM institutions WHERE public_id = ANY($1)", list(missing_orgs))
                    for r in i_rows:
                        inst_names[r["public_id"]] = r["name"]
                if user_ids:
                    u_rows = await um_conn.fetch("SELECT public_id, first_name, last_name, email FROM users WHERE public_id = ANY($1)", list(user_ids))
                    for r in u_rows:
                        full_name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip()
                        user_names[r["public_id"]] = full_name or r["email"] or str(r["public_id"])
            finally:
                await um_conn.close()
        except Exception:
            pass

        for r in requests:
            r.course_name = course_names.get(r.course_id)  # type: ignore[attr-defined]
            r.institution_name = inst_names.get(r.organization_id)  # type: ignore[attr-defined]
            r.requester_name = user_names.get(r.requested_by)  # type: ignore[attr-defined]

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
        await self._enrich_requests([request])
        return request

    async def get(self, course_request_id: int) -> CourseRequest:
        request = (
            await self.db.execute(select(CourseRequest).where(CourseRequest.public_id == course_request_id))
        ).scalar_one_or_none()
        if request is None:
            raise NotFoundError("Course request not found.", code="COURSE_REQUEST_NOT_FOUND")
        await self._enrich_requests([request])
        return request

    async def list_requests(self, query: ListQuery, *, organization_ids: tuple[int, ...] | None) -> tuple[list[CourseRequest], int, bool]:
        stmt = select(CourseRequest)
        if organization_ids is not None:  # None: every institution
            stmt = stmt.where(CourseRequest.organization_id.in_(organization_ids))
        if query.status:
            status_val = CourseRequestStatus.SUBMITTED if query.status.lower() in ("pending", "submitted") else query.status
            stmt = stmt.where(CourseRequest.status == status_val)
        stmt = stmt.order_by(
            CourseRequest.created_at.desc() if query.sort_order == "desc" else CourseRequest.created_at.asc()
        )
        items, total, is_exact = await paginate(self.db, stmt, query.page, query.per_page)
        await self._enrich_requests(items)
        return items, total, is_exact

    async def approve(self, actor_user_id: int, request: CourseRequest, data: ApproveRequest) -> Subscription:
        if request.status != CourseRequestStatus.SUBMITTED:
            raise BadRequestError("Only a pending request can be approved.", code="REQUEST_NOT_PENDING")

        seats = data.seats or request.requested_seats
        term_days = data.term_days or request.requested_term_days
        now = utcnow()

        existing_sub = (
            await self.db.execute(
                select(Subscription).where(
                    Subscription.organization_id == request.organization_id,
                    Subscription.course_id == request.course_id,
                    Subscription.status == SubscriptionStatus.ACTIVE,
                )
            )
        ).scalar_one_or_none()

        if existing_sub is not None:
            # Institution already has active subscription; mark request approved and return existing subscription
            request.status = CourseRequestStatus.APPROVED
            request.decided_by = actor_user_id
            request.decided_at = now
            write_event(
                self.db,
                event_type="course_request.decided",
                aggregate_id=request.id,
                payload={**_decision_payload(request), "decision": "approved", "note": "existing_subscription_retained"},
            )
            await self.db.commit()
            await sync_entitlement(self.redis, key_prefix=self.settings.ENTITLEMENT_KEY_PREFIX, subscription=existing_sub)
            return existing_sub

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
        await self._enrich_requests([request])
        return request
