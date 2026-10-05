"""Atomic seat reserve/release (see docs/PRODUCT.md §6.1: "Enrol student -> seat check: Sync
learning -> subscription (atomic seat reserve)"). Idempotent on ``reservation_key`` so a
retried call from another service never double-counts a seat — see app/models/seat_reservation.py.
"""

import uuid

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.time import utcnow
from app.db.session import commit_or_conflict
from app.domain.enums import SubscriptionStatus
from app.entitlements.cache import sync_entitlement
from app.models.seat_reservation import SeatReservation
from app.models.subscription import Subscription


class SeatService:
    def __init__(self, db: AsyncSession, settings: Settings, redis: Redis) -> None:
        self.db = db
        self.settings = settings
        self.redis = redis

    async def _locked_subscription(self, subscription_id: int) -> Subscription:
        subscription = (
            await self.db.execute(
                select(Subscription).where(Subscription.public_id == subscription_id).with_for_update()
            )
        ).scalar_one_or_none()
        if subscription is None:
            raise NotFoundError("Subscription not found.", code="SUBSCRIPTION_NOT_FOUND")
        return subscription

    async def reserve(self, subscription_id: int, reservation_key: str) -> Subscription:
        subscription = await self._locked_subscription(subscription_id)
        existing = await self._active_reservation(subscription.id, reservation_key)
        if existing is not None:
            return subscription  # idempotent: already reserved under this key

        if subscription.status != SubscriptionStatus.ACTIVE:
            raise BadRequestError("This subscription is not active.", code="SUBSCRIPTION_NOT_ACTIVE")
        if subscription.seats_used >= subscription.seats_total:
            raise BadRequestError("No seats are available on this subscription.", code="NO_SEATS_AVAILABLE")

        subscription.seats_used += 1
        self.db.add(SeatReservation(subscription_id=subscription.id, reservation_key=reservation_key))
        await commit_or_conflict(self.db)
        await sync_entitlement(self.redis, key_prefix=self.settings.ENTITLEMENT_KEY_PREFIX, subscription=subscription)
        return subscription

    async def release(self, subscription_id: int, reservation_key: str) -> Subscription:
        subscription = await self._locked_subscription(subscription_id)
        reservation = await self._active_reservation(subscription.id, reservation_key)
        if reservation is None:
            return subscription  # idempotent: already released or never reserved

        reservation.released_at = utcnow()
        subscription.seats_used = max(0, subscription.seats_used - 1)
        await self.db.commit()
        await sync_entitlement(self.redis, key_prefix=self.settings.ENTITLEMENT_KEY_PREFIX, subscription=subscription)
        return subscription

    async def _active_reservation(self, subscription_id: uuid.UUID, reservation_key: str) -> SeatReservation | None:
        return (
            await self.db.execute(
                select(SeatReservation).where(
                    SeatReservation.subscription_id == subscription_id,
                    SeatReservation.reservation_key == reservation_key,
                    SeatReservation.released_at.is_(None),
                )
            )
        ).scalar_one_or_none()
