from typing import Annotated

from fastapi import APIRouter, Depends, Query
from lms_common.envelopes import PageContext, SortOrder
from sqlalchemy import select

from app.api.deps import (
    CurrentAuth,
    DbSession,
    RedisDep,
    RequireAccountsManage,
    SettingsDep,
    SubscriptionIdParam,
    ensure_organization_visible,
    institutions_listed,
    require_seat_caller,
)
from app.api.responses import errors
from app.core.exceptions import NotFoundError
from app.core.time import utcnow
from app.domain.enums import SubscriptionStatus
from app.entitlements.cache import sync_entitlement
from app.models.subscription import Subscription
from app.schemas.common import ListQuery
from app.schemas.subscription import CancelRequest, SubscriptionListResponse, SubscriptionOut, SubscriptionResponse
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


@router.get(
    "/internal/organizations/{organization_id}/courses/{course_id}/active",
    summary="Get active subscription for an organization and course (internal)",
    dependencies=[Depends(require_seat_caller)],
)
async def get_active_subscription_internal(
    organization_id: int,
    course_id: int,
    db: DbSession,
    settings: SettingsDep,
    redis: RedisDep,
) -> dict:
    now = utcnow()
    stmt = (
        select(Subscription)
        .where(
            Subscription.organization_id == organization_id,
            Subscription.course_id == course_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.starts_at <= now,
            Subscription.ends_at >= now,
        )
    )
    sub = (await db.execute(stmt)).scalars().first()
    if sub is None:
        raise NotFoundError("No active subscription for this course and institution.", code="NO_ACTIVE_SUBSCRIPTION")

    await sync_entitlement(redis, key_prefix=settings.ENTITLEMENT_KEY_PREFIX, subscription=sub)
    return {
        "subscription_id": sub.public_id,
        "organization_id": sub.organization_id,
        "course_id": sub.course_id,
        "seats_total": sub.seats_total,
        "seats_used": sub.seats_used,
        "starts_at": sub.starts_at.isoformat(),
        "ends_at": sub.ends_at.isoformat(),
    }


@router.get(
    "",
    response_model=SubscriptionListResponse,
    summary="List subscriptions",
    description="An institution head sees only their own institution's subscriptions; accounts.manage sees all.",
    responses=errors(401, 422),
)
async def list_subscriptions(
    query: Annotated[ListQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> SubscriptionListResponse:
    organization_ids = institutions_listed(auth)
    subscriptions, total, is_exact = await SubscriptionService(db, settings, redis).list_subscriptions(
        query, organization_ids=organization_ids
    )
    return SubscriptionListResponse(
        message="Subscriptions retrieved successfully.",
        subscriptions=[SubscriptionOut.model_validate(subscription) for subscription in subscriptions],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Get a subscription",
    responses=errors(401, 403, 404),
)
async def get_subscription(
    subscription_id: SubscriptionIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> SubscriptionResponse:
    subscription = await SubscriptionService(db, settings, redis).get(subscription_id)
    ensure_organization_visible(auth, subscription.organization_id)
    return SubscriptionResponse(message="Subscription retrieved successfully.", subscription=SubscriptionOut.model_validate(subscription))


@router.post(
    "/{subscription_id}/cancel",
    response_model=SubscriptionResponse,
    summary="Cancel an active subscription",
    responses=errors(400, 401, 403, 404, 422),
)
async def cancel_subscription(
    subscription_id: SubscriptionIdParam,
    data: CancelRequest,
    auth: RequireAccountsManage,
    db: DbSession,
    settings: SettingsDep,
    redis: RedisDep,
) -> SubscriptionResponse:
    service = SubscriptionService(db, settings, redis)
    subscription = await service.get(subscription_id)
    subscription = await service.cancel(subscription, data.reason)
    return SubscriptionResponse(message="Subscription cancelled.", subscription=SubscriptionOut.model_validate(subscription))
