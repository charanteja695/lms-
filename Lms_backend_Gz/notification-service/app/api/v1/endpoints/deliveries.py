from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import DbSession, DeliveryIdParam, RequireSuperAdmin, SettingsDep, WriteRateLimit
from app.api.responses import errors
from app.schemas.common import DeliveryQuery
from app.schemas.delivery import DeliveryListResponse, DeliveryOut, DeliveryResponse
from app.services.delivery_service import DeliveryService

router = APIRouter(prefix="/deliveries", tags=["Deliveries"])


@router.get("", response_model=DeliveryListResponse, summary="List email deliveries", responses=errors(401, 403, 422, 429))
async def list_deliveries(
    query: Annotated[DeliveryQuery, Query()], auth: RequireSuperAdmin, db: DbSession, settings: SettingsDep
) -> DeliveryListResponse:
    deliveries, total, is_exact = await DeliveryService(db, settings).list_deliveries(query)
    return DeliveryListResponse(
        message="Deliveries retrieved successfully.",
        deliveries=[DeliveryOut.model_validate(delivery) for delivery in deliveries],
        page_context=PageContext.build(
            page=query.page,
            per_page=query.per_page,
            total=total,
            is_exact=is_exact,
            sort_column="created_time",
            sort_order=SortOrder(query.sort_order),
        ),
    )


@router.post(
    "/{delivery_id}/retry",
    response_model=DeliveryResponse,
    summary="Retry a failed delivery",
    responses=errors(400, 401, 403, 404, 429),
    dependencies=[WriteRateLimit],
)
async def retry_delivery(delivery_id: DeliveryIdParam, auth: RequireSuperAdmin, db: DbSession, settings: SettingsDep) -> DeliveryResponse:
    delivery = await DeliveryService(db, settings).retry(delivery_id)
    return DeliveryResponse(message="Delivery queued for retry.", delivery=DeliveryOut.model_validate(delivery))
