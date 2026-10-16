"""Quotes (docs/PRODUCT.md §5.10): an institution asks what a bundle of course seats would cost; an accepted quote fixes the price the
subscription's invoice will use when subscription-service later activates it."""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import tax
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import PriceKind, QuoteStatus
from app.models.billing import BillingProfile, Quote
from app.models.refs import OrgRef
from app.permissions.policy import can_manage_billing, owns
from app.services.outbox import write_event
from app.services.price_service import PriceService


def _iso(value: Any) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class QuoteService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def get(self, auth: AccessTokenClaims, public_id: int) -> Quote:
        quote = (await self.db.execute(select(Quote).where(Quote.public_id == public_id))).scalar_one_or_none()
        if quote is None or not owns(auth, quote.org_id):
            raise NotFoundError("Quote not found.", code="QUOTE_NOT_FOUND")
        return quote

    async def locked(self, quote: Quote) -> Quote:
        return (await self.db.execute(select(Quote).where(Quote.id == quote.id).with_for_update().execution_options(populate_existing=True))).scalar_one()

    async def list_quotes(self, auth: AccessTokenClaims, *, org_id: int | None, status: str | None, page: int, per_page: int) -> tuple[list[Quote], int]:
        stmt = select(Quote)
        if can_manage_billing(auth):
            if org_id is not None:
                stmt = stmt.where(Quote.org_id == org_id)
        else:
            stmt = stmt.where(Quote.org_id == auth.organization_id)
        if status:
            stmt = stmt.where(Quote.status == status)
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows: Any = (await self.db.execute(stmt.order_by(Quote.created_at.desc(), Quote.id).limit(per_page).offset((page - 1) * per_page))).scalars()
        return list(rows), total

    async def _totals(self, org_id: int, subtotal: int, discount: int) -> tuple[int, int, int]:
        """(discount applied, GST, total). GST uses the organisation's state if it has set a billing profile, otherwise the IGST case."""
        applied, taxable = tax.after_discount(subtotal, discount)
        profile = await self.db.get(BillingProfile, org_id)
        intra = profile is not None and tax.same_state(self.settings.SELLER_STATE, profile.state)
        cgst, sgst, igst = tax.gst(taxable, self.settings.GST_RATE_PERCENT, intra_state=intra)
        return applied, cgst + sgst + igst, taxable + cgst + sgst + igst

    async def create(self, auth: AccessTokenClaims, org_id: int, requested: list[dict[str, int]]) -> Quote:
        if not owns(auth, org_id):
            raise NotFoundError("Organisation not found.", code="ORGANIZATION_NOT_FOUND")
        ref = await self.db.get(OrgRef, org_id)
        if ref is not None and ref.org_type == "employer":
            # course seats are subscribed by institutions only (subscription-service); an employer buys plans instead
            raise ConflictError("Course seats are for institutions; a company buys an employer plan.", code="NOT_AN_INSTITUTION")
        if not requested or len(requested) > self.settings.MAX_QUOTE_LINES:
            raise ValidationFailedError(details=[{"field": "lines", "code": "OUT_OF_RANGE", "message": f"Ask about 1-{self.settings.MAX_QUOTE_LINES} courses"}])
        prices = PriceService(self.db)
        lines: list[dict[str, Any]] = []
        for index, item in enumerate(requested):
            price = await prices.by_code(PriceKind.COURSE_SEAT, str(item["course_id"]))
            if price is None:
                raise ValidationFailedError(details=[{"field": f"lines.{index}.course_id", "code": "NO_PRICE", "message": "There is no price for this course yet: ask the platform team"}])
            lines.append(
                {
                    "course_id": str(item["course_id"]), "name": price.name, "seats": item["seats"], "term_days": item["term_days"], "unit_amount": price.unit_amount,
                    "amount": tax.prorate(price.unit_amount, item["seats"], item["term_days"]), "invoiced": False,
                }
            )
        subtotal = sum(line["amount"] for line in lines)
        _, gst_total, total = await self._totals(org_id, subtotal, 0)
        quote = Quote(
            public_id=new_public_id(), org_id=org_id, requested_by=auth.user_id, status=QuoteStatus.OPEN, lines=lines, subtotal=subtotal, discount=0, gst=gst_total, total=total,
            valid_until=utcnow() + timedelta(days=self.settings.QUOTE_VALID_DAYS),
        )
        self.db.add(quote)
        await self.db.flush()
        self._event("quote.created", quote)
        await self.db.commit()
        return quote

    async def discount(self, quote: Quote, *, amount: int, note: str) -> Quote:
        quote = await self.locked(quote)
        if quote.status != QuoteStatus.OPEN:
            raise ConflictError(f"This quote is {quote.status}.", code="QUOTE_NOT_OPEN")
        applied, gst_total, total = await self._totals(quote.org_id, quote.subtotal, amount)
        quote.discount, quote.discount_note, quote.gst, quote.total = applied, note, gst_total, total
        await self.db.commit()
        return quote

    async def accept(self, quote: Quote) -> Quote:
        quote = await self.locked(quote)
        if quote.status != QuoteStatus.OPEN:
            raise ConflictError(f"This quote is {quote.status}.", code="QUOTE_NOT_OPEN")
        if quote.valid_until < utcnow():
            quote.status = QuoteStatus.EXPIRED
            self._event("quote.expired", quote)
            await self.db.commit()
            raise ConflictError("This quote has expired: ask for a new one.", code="QUOTE_EXPIRED")
        quote.status, quote.accepted_at = QuoteStatus.ACCEPTED, utcnow()
        self._event("quote.accepted", quote)
        await self.db.commit()
        return quote

    async def cancel(self, quote: Quote) -> Quote:
        quote = await self.locked(quote)
        if quote.status != QuoteStatus.OPEN:
            raise ConflictError(f"This quote is {quote.status}.", code="QUOTE_NOT_OPEN")
        quote.status = QuoteStatus.CANCELLED
        await self.db.commit()
        return quote

    def _event(self, event_type: str, quote: Quote) -> None:
        write_event(
            self.db, event_type=event_type, aggregate_type="quote", aggregate_id=quote.id,
            payload={"quote_id": str(quote.public_id), "organization_id": str(quote.org_id), "total_amount": quote.total, "status": quote.status, "occurred_at": _iso(utcnow())},
        )

    async def expire_stale(self, *, limit: int = 200) -> int:
        rows = list(
            (await self.db.execute(select(Quote).where(Quote.status == QuoteStatus.OPEN, Quote.valid_until < utcnow()).limit(limit).with_for_update(skip_locked=True))).scalars()
        )
        for quote in rows:
            quote.status = QuoteStatus.EXPIRED
            self._event("quote.expired", quote)
        await self.db.commit()
        return len(rows)

    async def take_for_subscription(self, org_id: int, course_id: str, seats: int) -> tuple[Quote, dict[str, Any]] | None:
        """An accepted quote line that covers this subscription (same course, same seats) and has not been invoiced yet: its price is the one to use."""
        quotes = (
            await self.db.execute(
                select(Quote).where(Quote.org_id == org_id, Quote.status == QuoteStatus.ACCEPTED, Quote.used_at.is_(None)).order_by(Quote.accepted_at).with_for_update()
            )
        ).scalars()
        for quote in quotes:
            for index, line in enumerate(quote.lines):
                if line["course_id"] == course_id and line["seats"] == seats and not line["invoiced"]:
                    updated = [dict(item) for item in quote.lines]
                    updated[index]["invoiced"] = True
                    quote.lines = updated  # a new list: SQLAlchemy does not see an in-place change to a JSON column
                    if all(item["invoiced"] for item in updated):
                        quote.used_at = utcnow()
                    return quote, line
        return None
