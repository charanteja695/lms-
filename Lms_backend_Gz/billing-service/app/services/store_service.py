"""The learner store: a self-registered learner (``store.buy``) buys a course for themselves.

buy      -> a CoursePurchase + an invoice issued to them at once + a Razorpay order for its total
confirm  -> the browser's Razorpay signature is verified, the payment captured, the invoice paid
paid     -> InvoiceService announces ``course.purchased``; subscription-service grants or extends their access
The webhook captures the same payment if the browser never comes back; capturing twice changes nothing.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import tax
from app.core.config import Settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, UpstreamUnavailableError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.domain.enums import InvoiceKind, InvoiceStatus, PaymentMethod, PaymentStatus, PriceKind, PurchaseStatus
from app.gateways.errors import Rejected, Unavailable
from app.gateways.payment import PaymentGateway, PaymentGatewayNotConfigured
from app.models.billing import CoursePurchase, Invoice, Payment, PriceItem
from app.services.invoice_service import InvoiceService
from app.services.payment_service import PaymentService
from app.services.price_service import PriceService


@dataclass(frozen=True, slots=True)
class Offer:
    course_id: int
    name: str
    price: int  # before GST, paise
    gst: int
    total: int  # what the learner pays
    valid_days: int


@dataclass(frozen=True, slots=True)
class Checkout:
    provider: str
    key_id: str | None
    order_id: str
    amount: int
    currency: str
    seller_name: str


class StoreService:
    def __init__(self, db: AsyncSession, settings: Settings, gateway: PaymentGateway | None = None) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway or PaymentGateway(settings)
        self.invoices = InvoiceService(db, settings)
        self.payments = PaymentService(db, settings, self.gateway)

    def _offer(self, price: PriceItem) -> Offer:
        cgst, sgst, igst = tax.gst(price.unit_amount, self.settings.GST_RATE_PERCENT, intra_state=True)
        gst = cgst + sgst + igst
        days = int((price.meta or {}).get("valid_days") or self.settings.LEARNER_ACCESS_DAYS)
        return Offer(course_id=int(price.code), name=price.name, price=price.unit_amount, gst=gst, total=price.unit_amount + gst, valid_days=days)

    async def offers(self) -> list[Offer]:
        prices, _ = await PriceService(self.db).list_prices(kind=PriceKind.COURSE_SEAT.value, include_inactive=False, page=1, per_page=100)
        return [self._offer(p) for p in prices if p.code.isdigit()]

    async def mine(self, auth: AccessTokenClaims) -> list[tuple[CoursePurchase, Invoice]]:
        rows = (
            await self.db.execute(
                select(CoursePurchase, Invoice)
                .join(Invoice, Invoice.id == CoursePurchase.invoice_id)
                .where(CoursePurchase.user_id == auth.user_id, CoursePurchase.status != PurchaseStatus.CANCELLED)
                .order_by(CoursePurchase.created_at.desc())
            )
        ).all()
        return [(p, i) for p, i in rows]

    async def get_own(self, auth: AccessTokenClaims, purchase_id: int) -> tuple[CoursePurchase, Invoice]:
        row = (
            await self.db.execute(
                select(CoursePurchase, Invoice).join(Invoice, Invoice.id == CoursePurchase.invoice_id).where(CoursePurchase.public_id == purchase_id, CoursePurchase.user_id == auth.user_id)
            )
        ).first()
        if row is None:
            raise NotFoundError("Purchase not found.", code="PURCHASE_NOT_FOUND")
        return row[0], row[1]

    async def buy(self, auth: AccessTokenClaims, course_id: int, *, name: str, email: str | None) -> tuple[CoursePurchase, Checkout]:
        """Start (or restart) paying for a course. Buying a course you already have extends your access by its period."""
        if not self.gateway.configured:
            raise UpstreamUnavailableError("Online payment is not available right now. Please try again later.", code="PAYMENT_GATEWAY_NOT_CONFIGURED")
        price = await PriceService(self.db).by_code(PriceKind.COURSE_SEAT, str(course_id))
        if price is None:
            raise NotFoundError("This course is not on sale.", code="COURSE_NOT_ON_SALE")
        org_id = auth.organization_id or 0
        pending = (
            await self.db.execute(
                select(CoursePurchase).where(CoursePurchase.user_id == auth.user_id, CoursePurchase.course_id == course_id, CoursePurchase.status == PurchaseStatus.PENDING)
            )
        ).scalar_one_or_none()
        if pending is not None:
            invoice = (await self.db.execute(select(Invoice).where(Invoice.id == pending.invoice_id))).scalar_one()
            return pending, await self._checkout(invoice, pending)

        offer = self._offer(price)
        purchase_public_id = new_public_id()
        draft = await self.invoices.create_draft(
            org_id=org_id, kind=InvoiceKind.COURSE, source_type="purchase", source_id=str(purchase_public_id),
            lines=[{"description": f"{price.name}: {offer.valid_days} days' access", "quantity": 1, "unit_amount": price.unit_amount}],
        )
        if draft is None:  # cannot happen for a fresh public id; kept so the type is honest
            raise ConflictError("The invoice could not be created.", code="INVOICE_EXISTS")
        purchase = CoursePurchase(
            public_id=purchase_public_id, org_id=org_id, user_id=auth.user_id, course_id=course_id, course_name=price.name[:160], valid_days=offer.valid_days,
            amount=offer.total, status=PurchaseStatus.PENDING, invoice_id=draft.id,
        )
        self.db.add(purchase)
        await self.db.flush()
        invoice = await self.invoices.issue(draft, person={"name": name, "email": email})  # commits
        purchase.amount = invoice.total
        await self.db.commit()
        return purchase, await self._checkout(invoice, purchase)

    async def _checkout(self, invoice: Invoice, purchase: CoursePurchase) -> Checkout:
        if invoice.status not in (InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE):
            raise ConflictError(f"This purchase's invoice is {invoice.status}.", code="INVOICE_NOT_PAYABLE")
        amount = self.invoices.owed(invoice)
        try:
            order = await self.gateway.create_order(
                amount=amount, currency=invoice.currency, receipt=invoice.number or str(invoice.public_id),
                notes={"purchase_id": str(purchase.public_id), "course_id": str(purchase.course_id), "user_id": str(purchase.user_id)},
            )
        except PaymentGatewayNotConfigured as exc:
            raise UpstreamUnavailableError("Online payment is not available right now. Please try again later.", code="PAYMENT_GATEWAY_NOT_CONFIGURED") from exc
        except (Unavailable, Rejected) as exc:
            raise UpstreamUnavailableError("The payment provider could not start the payment. Please try again.", code="PAYMENT_GATEWAY_UNAVAILABLE") from exc
        self.db.add(Payment(public_id=new_public_id(), invoice_id=invoice.id, method=PaymentMethod.GATEWAY, status=PaymentStatus.PENDING, amount=amount, gateway_order_id=order.order_id))
        try:
            await self.db.commit()
        except IntegrityError as exc:  # the provider handed back an order id already used: never two payments on one order
            await self.db.rollback()
            raise UpstreamUnavailableError("The payment provider could not start the payment. Please try again.", code="PAYMENT_GATEWAY_UNAVAILABLE") from exc
        return Checkout(
            provider=self.settings.PAYMENT_PROVIDER, key_id=self.gateway.public_key, order_id=order.order_id, amount=order.amount, currency=order.currency,
            seller_name=self.settings.SELLER_DISPLAY_NAME,
        )

    async def confirm(self, auth: AccessTokenClaims, purchase_id: int, *, order_id: str, payment_id: str, signature: str) -> tuple[CoursePurchase, Invoice]:
        """The browser came back from the checkout. The signature proves the payment; the money is captured once only."""
        purchase, invoice = await self.get_own(auth, purchase_id)
        belongs = (await self.db.execute(select(Payment.id).where(Payment.invoice_id == invoice.id, Payment.gateway_order_id == order_id))).first()
        if belongs is None or not self.gateway.checkout_signature_valid(order_id=order_id, payment_id=payment_id, signature=signature):
            raise BadRequestError("The payment could not be verified. If money was taken, it is confirmed automatically within minutes.", code="PAYMENT_NOT_VERIFIED")
        await self.payments.capture(order_id, payment_id, None)
        return await self.get_own(auth, purchase_id)

