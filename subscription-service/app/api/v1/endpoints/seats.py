"""Seat reserve/release: called synchronously by learning-service on enrol/withdraw (see
docs/PRODUCT.md §6.1), authenticated via the shared internal-service token (or a human
accounts.manage admin for support/ops use) — see app/api/deps.py::require_seat_caller.
"""

from fastapi import APIRouter, Depends

from app.api.deps import (
    CurrentAuth,
    DbSession,
    RedisDep,
    SettingsDep,
    SubscriptionIdParam,
    ensure_organization_visible,
    require_seat_caller,
)
from app.api.responses import errors
from app.models.subscription import Subscription
from app.schemas.seat import SeatReleaseRequest, SeatReserveRequest, SeatStatusOut, SeatStatusResponse
from app.services.seat_service import SeatService
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions/{subscription_id}/seats", tags=["Seats"])


def _status(subscription: Subscription) -> SeatStatusOut:
    return SeatStatusOut(
        seats_total=subscription.seats_total,
        seats_used=subscription.seats_used,
        seats_available=max(0, subscription.seats_total - subscription.seats_used),
    )


@router.get("", response_model=SeatStatusResponse, summary="Get seat availability", responses=errors(401, 403, 404))
async def get_seats(
    subscription_id: SubscriptionIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> SeatStatusResponse:
    subscription = await SubscriptionService(db, settings, redis).get(subscription_id)
    ensure_organization_visible(auth, subscription.organization_id)
    return SeatStatusResponse(message="Seat availability retrieved successfully.", seats=_status(subscription))


@router.post(
    "/reserve",
    response_model=SeatStatusResponse,
    summary="Reserve a seat",
    responses=errors(400, 401, 403, 404, 422),
    dependencies=[Depends(require_seat_caller)],
)
async def reserve_seat(
    subscription_id: SubscriptionIdParam, data: SeatReserveRequest, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> SeatStatusResponse:
    subscription = await SeatService(db, settings, redis).reserve(subscription_id, data.reservation_key)
    return SeatStatusResponse(message="Seat reserved.", seats=_status(subscription))


@router.post(
    "/release",
    response_model=SeatStatusResponse,
    summary="Release a seat",
    responses=errors(400, 401, 403, 404, 422),
    dependencies=[Depends(require_seat_caller)],
)
async def release_seat(
    subscription_id: SubscriptionIdParam, data: SeatReleaseRequest, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> SeatStatusResponse:
    subscription = await SeatService(db, settings, redis).release(subscription_id, data.reservation_key)
    return SeatStatusResponse(message="Seat released.", seats=_status(subscription))
