"""Inbound event handlers (payload contracts of the producers).

  institution.* / employer.*    user-management: {organization_id, name, organization_type, status} — who can be billed
  subscription.activated        subscription-service: {subscription_id, organization_id, course_id, seats_total, ends_at} — drafts the institution's invoice.
                                The price is the one on an accepted quote covering this course and seat count, else the price list's, else 0 with a
                                note on the draft ("No price configured"): a billing admin fixes the draft and issues it.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import tax
from app.core.config import Settings
from app.domain.enums import InvoiceKind, PriceKind
from app.models.refs import OrgRef
from app.services.invoice_service import InvoiceService
from app.services.price_service import PriceService
from app.services.quote_service import QuoteService


def _int(value: Any) -> int | None:
    try:
        return int(str(value)) if value not in (None, "") else None
    except ValueError:
        return None


async def handle_org_upserted(db: AsyncSession, settings: Settings, payload: dict[str, Any], occurred_time: datetime) -> None:
    org_id = _int(payload.get("organization_id"))
    if org_id is None:
        return
    ref = await db.get(OrgRef, org_id)
    if ref is None:
        ref = OrgRef(org_id=org_id)
        db.add(ref)
    ref.name = str(payload.get("name") or ref.name or "")[:200]
    ref.org_type = str(payload.get("organization_type") or ref.org_type or "")[:12]
    ref.active = payload.get("status", "active") == "active"


async def handle_org_deleted(db: AsyncSession, settings: Settings, payload: dict[str, Any], occurred_time: datetime) -> None:
    org_id = _int(payload.get("organization_id"))
    ref = await db.get(OrgRef, org_id) if org_id is not None else None
    if ref is not None:
        ref.active = False


async def handle_subscription_activated(db: AsyncSession, settings: Settings, payload: dict[str, Any], occurred_time: datetime) -> None:
    org_id, subscription_id, seats = _int(payload.get("organization_id")), payload.get("subscription_id"), _int(payload.get("seats_total"))
    course_id = str(payload.get("course_id") or "")
    if org_id is None or not subscription_id or not seats or not course_id:
        return
    try:
        ends_at = datetime.fromisoformat(str(payload["ends_at"]))
    except (KeyError, ValueError):
        return
    start = occurred_time if occurred_time.tzinfo else occurred_time.replace(tzinfo=UTC)
    end = ends_at if ends_at.tzinfo else ends_at.replace(tzinfo=UTC)
    term_days = max((end - start).days, 1)

    quote_id: Any = None
    discount = 0
    note: str | None = None
    taken = await QuoteService(db, settings).take_for_subscription(org_id, course_id, seats)
    price = await PriceService(db).by_code(PriceKind.COURSE_SEAT, course_id)
    name = price.name if price else f"Course {course_id}"
    if taken is not None:
        quote, line = taken
        quote_id = quote.id
        amount = tax.prorate(int(line["unit_amount"]), seats, term_days)
        discount = quote.discount * int(line["amount"]) // quote.subtotal if quote.subtotal else 0  # the quote's discount, in proportion to this line
    elif price is not None:
        amount = tax.prorate(price.unit_amount, seats, term_days)
    else:
        amount, note = 0, f"No price configured for course {course_id}: set the line's price, then issue."
    await InvoiceService(db, settings).create_draft(
        org_id=org_id, kind=InvoiceKind.SUBSCRIPTION, source_type="subscription", source_id=str(subscription_id),
        lines=[{"description": f"{name} - {seats} seats, {term_days} days", "quantity": 1, "unit_amount": amount, "amount": amount}], discount=discount, quote_id=quote_id, note=note,
    )
