"""A self-registered learner's bought course access (``course.purchased`` from billing-service).

  first purchase           -> access from now for ``valid_days``           -> course_access.granted
  again, while active      -> ends_at moves out by ``valid_days``           -> course_access.extended
  again, after it expired  -> a fresh period from now                       -> course_access.granted
  ends_at passes           -> expired (worker sweep)                        -> course_access.expired
learning-service enrols and un-enrols the learner from these events; this service never calls it.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import new_public_id
from app.core.time import utcnow
from app.domain.enums import CourseAccessStatus
from app.models.course_access import CourseAccess, CourseAccessPurchase
from app.services.outbox import write_event


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _payload(access: CourseAccess) -> dict[str, Any]:
    return {
        "access_id": str(access.public_id), "user_id": str(access.user_id), "organization_id": str(access.organization_id),
        "course_id": str(access.course_id), "starts_at": _iso(access.starts_at), "ends_at": _iso(access.ends_at),
    }


class CourseAccessService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def mine(self, user_id: int) -> list[CourseAccess]:
        return list((await self.db.execute(select(CourseAccess).where(CourseAccess.user_id == user_id).order_by(CourseAccess.ends_at.desc()))).scalars())

    async def apply_purchase(self, payload: dict[str, Any]) -> None:
        """Idempotent per purchase: a redelivered event changes nothing."""
        purchase_id, user_id, course_id = int(payload["purchase_id"]), int(payload["user_id"]), int(payload["course_id"])
        days = int(payload["valid_days"])
        if await self.db.get(CourseAccessPurchase, purchase_id) is not None:
            return
        now = utcnow()
        access = (
            await self.db.execute(select(CourseAccess).where(CourseAccess.user_id == user_id, CourseAccess.course_id == course_id).with_for_update())
        ).scalar_one_or_none()
        if access is None:
            access = CourseAccess(
                public_id=new_public_id(), user_id=user_id, organization_id=int(payload["organization_id"]), course_id=course_id,
                starts_at=now, ends_at=now + timedelta(days=days), status=CourseAccessStatus.ACTIVE,
            )
            self.db.add(access)
            event = "course_access.granted"
        elif access.status == CourseAccessStatus.ACTIVE and access.ends_at > now:
            access.ends_at = access.ends_at + timedelta(days=days)
            event = "course_access.extended"
        else:
            access.starts_at, access.ends_at, access.status = now, now + timedelta(days=days), CourseAccessStatus.ACTIVE
            event = "course_access.granted"
        await self.db.flush()
        self.db.add(CourseAccessPurchase(purchase_id=purchase_id, access_id=access.id, valid_days=days))
        write_event(self.db, event_type=event, aggregate_id=access.id, payload={**_payload(access), "purchase_id": str(purchase_id)})

    async def expire_due(self) -> int:
        due = list(
            (
                await self.db.execute(
                    select(CourseAccess).where(CourseAccess.status == CourseAccessStatus.ACTIVE, CourseAccess.ends_at <= utcnow()).limit(500).with_for_update(skip_locked=True)
                )
            ).scalars()
        )
        for access in due:
            access.status = CourseAccessStatus.EXPIRED
            write_event(self.db, event_type="course_access.expired", aggregate_id=access.id, payload=_payload(access))
        if due:
            await self.db.commit()
        return len(due)
