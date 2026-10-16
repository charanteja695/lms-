"""Quotes: an institution asks for a price, a billing manager may discount it, the institution accepts it, and the accepted price is what its
subscription's invoice uses when subscription-service activates the subscription."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    DbSession,
    QuoteIdParam,
    RequireBillingAdmin,
    RequireBillingContact,
    SettingsDep,
    WriteRateLimit,
)
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import ValidationFailedError
from app.core.ids import parse_public_id
from app.domain.enums import QuoteStatus
from app.permissions.policy import can_manage_billing
from app.schemas.billing import DiscountIn, QuoteCreate, QuoteOut, QuotePage, QuoteResponse
from app.services.quote_service import QuoteService

router = APIRouter(prefix="/quotes", tags=["Quotes"])
admin = APIRouter(prefix="/admin/quotes", tags=["Quotes (admin)"])


@router.post("", response_model=QuoteResponse, status_code=201, summary="Ask for a price", responses=errors(*AUTHENTICATED), dependencies=[WriteRateLimit],
             description="Prices come from the price list; GST uses your billing profile's state (IGST until you set one). An open quote lasts `QUOTE_VALID_DAYS`.")
async def create_quote(body: QuoteCreate, auth: RequireBillingContact, db: DbSession, settings: SettingsDep) -> QuoteResponse:
    org_id = body.organization_id if body.organization_id is not None and can_manage_billing(auth) else auth.organization_id
    if org_id is None:
        raise ValidationFailedError(details=[{"field": "organization_id", "code": "REQUIRED", "message": "Name the organisation to quote"}])
    quote = await QuoteService(db, settings).create(auth, org_id, [{"course_id": int(line.course_id), "seats": line.seats, "term_days": line.term_days} for line in body.lines])
    return QuoteResponse(message="Quote ready.", quote=QuoteOut.model_validate(quote))


@router.get("", response_model=QuotePage, summary="My organisation's quotes", responses=errors(*AUTHENTICATED))
async def list_quotes(
    auth: RequireBillingContact, db: DbSession, settings: SettingsDep, status: Annotated[QuoteStatus | None, Query()] = None,
    organization_id: Annotated[str | None, Query(description="Billing managers: one organisation's quotes")] = None, page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> QuotePage:
    org = parse_public_id(organization_id) if organization_id and can_manage_billing(auth) else None
    quotes, total = await QuoteService(db, settings).list_quotes(auth, org_id=org, status=status.value if status else None, page=page, per_page=per_page)
    return QuotePage(
        message="", quotes=[QuoteOut.model_validate(q) for q in quotes],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


@router.get("/{quote_id}", response_model=QuoteResponse, summary="A quote", responses=errors(*AUTHENTICATED, 404))
async def get_quote(quote_id: QuoteIdParam, auth: RequireBillingContact, db: DbSession, settings: SettingsDep) -> QuoteResponse:
    return QuoteResponse(message="", quote=QuoteOut.model_validate(await QuoteService(db, settings).get(auth, quote_id)))


@router.post("/{quote_id}/accept", response_model=QuoteResponse, summary="Accept a quote", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit],
             description="Fixes the price: it does not itself create a subscription (subscription-service's own approval does that).")
async def accept_quote(quote_id: QuoteIdParam, auth: RequireBillingContact, db: DbSession, settings: SettingsDep) -> QuoteResponse:
    service = QuoteService(db, settings)
    return QuoteResponse(message="Accepted.", quote=QuoteOut.model_validate(await service.accept(await service.get(auth, quote_id))))


@router.post("/{quote_id}/cancel", response_model=QuoteResponse, summary="Cancel an open quote", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit])
async def cancel_quote(quote_id: QuoteIdParam, auth: RequireBillingContact, db: DbSession, settings: SettingsDep) -> QuoteResponse:
    service = QuoteService(db, settings)
    return QuoteResponse(message="Cancelled.", quote=QuoteOut.model_validate(await service.cancel(await service.get(auth, quote_id))))


@admin.post("/{quote_id}/discount", response_model=QuoteResponse, summary="Apply a discount to an open quote", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit])
async def discount_quote(quote_id: QuoteIdParam, body: DiscountIn, auth: RequireBillingAdmin, db: DbSession, settings: SettingsDep) -> QuoteResponse:
    service = QuoteService(db, settings)
    return QuoteResponse(message="Discount applied.", quote=QuoteOut.model_validate(await service.discount(await service.get(auth, quote_id), amount=body.amount, note=body.note)))
