"""The price list: what a course seat costs per 365 days and what each employer plan tier costs."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import DbSession, PriceIdParam, RequireBillingAdmin, RequireBillingContact, WriteRateLimit
from app.api.responses import AUTHENTICATED, errors
from app.domain.enums import PriceKind
from app.models.billing import PriceItem
from app.schemas.billing import PriceCreate, PriceOut, PricePage, PriceResponse, PriceUpdate
from app.services.price_service import PriceService

router = APIRouter(prefix="/prices", tags=["Prices"])
admin = APIRouter(prefix="/admin/prices", tags=["Prices (admin)"])


def _page(prices: list[PriceItem], total: int, page: int, per_page: int) -> PricePage:
    return PricePage(
        message="", prices=[PriceOut.model_validate(p) for p in prices],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="code", sort_order=SortOrder.ASC),
    )


@router.get("", response_model=PricePage, summary="Active prices", responses=errors(*AUTHENTICATED))
async def list_prices(
    auth: RequireBillingContact, db: DbSession, kind: Annotated[PriceKind | None, Query()] = None, page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 50
) -> PricePage:
    prices, total = await PriceService(db).list_prices(kind=kind.value if kind else None, include_inactive=False, page=page, per_page=per_page)
    return _page(prices, total, page, per_page)


@admin.get("", response_model=PricePage, summary="Every price, including inactive ones", responses=errors(*AUTHENTICATED))
async def list_all_prices(
    auth: RequireBillingAdmin, db: DbSession, kind: Annotated[PriceKind | None, Query()] = None, page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 50
) -> PricePage:
    prices, total = await PriceService(db).list_prices(kind=kind.value if kind else None, include_inactive=True, page=page, per_page=per_page)
    return _page(prices, total, page, per_page)


@admin.post("", response_model=PriceResponse, status_code=201, summary="Add a price", responses=errors(*AUTHENTICATED, 409), dependencies=[WriteRateLimit])
async def create_price(body: PriceCreate, auth: RequireBillingAdmin, db: DbSession) -> PriceResponse:
    meta = {"job_posts": body.job_posts, "valid_days": body.valid_days} if body.kind == PriceKind.EMPLOYER_PLAN else {}
    item = await PriceService(db).create({"kind": body.kind.value, "code": body.code, "name": body.name, "unit_amount": body.unit_amount, "meta": meta})
    return PriceResponse(message="Price added.", price=PriceOut.model_validate(item))


@admin.patch("/{price_id}", response_model=PriceResponse, summary="Change a price", responses=errors(*AUTHENTICATED, 404), dependencies=[WriteRateLimit],
             description="Invoices and quotes already made keep the amount they used.")
async def update_price(price_id: PriceIdParam, body: PriceUpdate, auth: RequireBillingAdmin, db: DbSession) -> PriceResponse:
    service = PriceService(db)
    item = await service.update(await service.get(price_id), body.model_dump(exclude_unset=True))
    return PriceResponse(message="Saved.", price=PriceOut.model_validate(item))
