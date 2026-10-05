from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    CurrentAuth,
    DbSession,
    RedisDep,
    RequireAccountsManage,
    SettingsDep,
    SubscriptionIdParam,
    ensure_organization_visible,
)
from app.api.responses import errors
from app.permissions.scopes import Scope
from app.schemas.common import ListQuery
from app.schemas.subscription import CancelRequest, SubscriptionListResponse, SubscriptionOut, SubscriptionResponse
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


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
    organization_id = None if auth.has_scope(Scope.ACCOUNTS_MANAGE.value) else auth.organization_id
    subscriptions, total, is_exact = await SubscriptionService(db, settings, redis).list_subscriptions(
        query, organization_id=organization_id
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
