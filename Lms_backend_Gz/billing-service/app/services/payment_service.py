"""Payments against an issued invoice (docs/PRODUCT.md §5.10): an admin records money received outside the platform (always available), or an
organisation pays through the payment gateway — a contract only (D13), so `503 PAYMENT_GATEWAY_NOT_CONFIGURED` until one is wired. A partial
payment is allowed; an invoice is paid once payments cover what remains after credit notes."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AppError, ConflictError, UpstreamUnavailableError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import InvoiceStatus, PaymentMethod, PaymentStatus
from app.gateways.errors import Rejected, Unavailable
from app.gateways.payment import PaymentGateway, PaymentGatewayNotConfigured
from app.models.billing import GatewayEvent, Invoice, Payment
from app.services.invoice_service import InvoiceService

_PAYABLE = {InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE}


class WebhookRejected(AppError):
    status_code = 401
    code = "INVALID_SIGNATURE"
    message = "The webhook signature is not valid."


class PaymentService:
    def __init__(self, db: AsyncSession, settings: Settings, gateway: PaymentGateway | None = None) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway or PaymentGateway(settings)
        self.invoices = InvoiceService(db, settings)

    async def list_for_invoice(self, invoice: Invoice) -> list[Payment]:
        return list((await self.db.execute(select(Payment).where(Payment.invoice_id == invoice.id).order_by(Payment.created_at))).scalars())

    def _require_payable(self, invoice: Invoice, amount: int) -> None:
        if invoice.status not in _PAYABLE:
            raise ConflictError(f"This invoice is {invoice.status}.", code="INVOICE_NOT_PAYABLE")
        if amount <= 0:
            raise ValidationFailedError(details=[{"field": "amount", "code": "INVALID_AMOUNT", "message": "Pay an amount greater than zero"}])
        if amount > self.invoices.owed(invoice):
            raise ConflictError("That is more than the invoice still owes.", code="AMOUNT_EXCEEDS_BALANCE")

    async def record_manual(self, auth: AccessTokenClaims, invoice: Invoice, *, amount: int, reference: str, method_note: str | None) -> Payment:
        invoice = await self.invoices.locked(invoice)
        self._require_payable(invoice, amount)
        payment = Payment(
            public_id=new_public_id(), invoice_id=invoice.id, method=PaymentMethod.MANUAL, status=PaymentStatus.SUCCEEDED, amount=amount, reference=(f"{reference} ({method_note})" if method_note else reference)[:120],
            recorded_by=auth.user_id, paid_at=utcnow(),
        )
        self.db.add(payment)
        await self._apply(invoice, amount)
        await self.db.commit()
        return payment

    async def _apply(self, invoice: Invoice, amount: int) -> None:
        invoice.amount_paid += amount
        await self.db.flush()
        await self.invoices.settle(invoice)

    # ------------------------------------------------------------------ the gateway
    async def start_gateway_payment(self, invoice: Invoice, *, amount: int | None) -> tuple[Payment, str]:
        """Create an order with the gateway for ``amount`` (default: everything still owed) and remember it. Nothing is held open across the call."""
        pay = amount if amount is not None else self.invoices.owed(invoice)
        self._require_payable(invoice, pay)
        try:
            order = await self.gateway.create_order(amount=pay, currency=invoice.currency, receipt=invoice.number or str(invoice.public_id))
        except PaymentGatewayNotConfigured as exc:
            raise UpstreamUnavailableError("Online payment is not available: pay by bank transfer and ask the platform team to record it.", code="PAYMENT_GATEWAY_NOT_CONFIGURED") from exc
        except (Unavailable, Rejected) as exc:
            raise UpstreamUnavailableError("The payment provider could not start the payment. Please try again.", code="PAYMENT_GATEWAY_UNAVAILABLE") from exc
        payment = Payment(public_id=new_public_id(), invoice_id=invoice.id, method=PaymentMethod.GATEWAY, status=PaymentStatus.PENDING, amount=pay, gateway_order_id=order.order_id)
        self.db.add(payment)
        await self.db.commit()
        return payment, order.order_id

    async def handle_webhook(self, body: bytes, headers: dict[str, str]) -> str:
        """The gateway's callback. Verified, de-duplicated by its event id, then applied under the invoice's lock. Returns what was done."""
        try:
            event = self.gateway.read_webhook(body, headers)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValidationFailedError(details=[{"field": "body", "code": "INVALID_EVENT", "message": "The event is missing its order or type"}]) from exc
        if event is None:
            raise WebhookRejected
        self.db.add(GatewayEvent(event_id=event.event_id[:80], received_at=utcnow()))
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            return "duplicate"
        if event.kind == "payment.captured":
            return await self.capture(event.order_id, event.payment_id, event.amount)
        if event.kind == "payment.failed":
            return await self.fail(event.order_id)
        await self.db.commit()
        return "ignored"

    async def _pending_payment(self, order_id: str) -> tuple[Payment, Invoice] | None:
        payment = (await self.db.execute(select(Payment).where(Payment.gateway_order_id == order_id))).scalar_one_or_none()
        if payment is None:
            return None
        invoice = await self.invoices.locked(await self._invoice_of(payment))
        payment = (await self.db.execute(select(Payment).where(Payment.id == payment.id).with_for_update().execution_options(populate_existing=True))).scalar_one()
        return payment, invoice

    async def capture(self, order_id: str, payment_id: str | None, amount: int | None) -> str:
        """Money for this order arrived (from the webhook or a verified checkout). Idempotent: a second report changes nothing."""
        found = await self._pending_payment(order_id)
        if found is None:
            await self.db.commit()
            return "ignored"
        payment, invoice = found
        if payment.status != PaymentStatus.PENDING:
            await self.db.commit()
            return "ignored"
        reused = payment_id is not None and (
            await self.db.execute(select(Payment.id).where(Payment.gateway_payment_id == payment_id, Payment.id != payment.id))
        ).first() is not None  # one provider payment settles one order, never two
        if reused or (amount is not None and amount != payment.amount) or invoice.status not in _PAYABLE or payment.amount > self.invoices.owed(invoice):
            payment.status = PaymentStatus.FAILED
            await self.db.commit()
            return "rejected"
        payment.status, payment.paid_at = PaymentStatus.SUCCEEDED, utcnow()
        payment.gateway_payment_id = payment_id
        await self._apply(invoice, payment.amount)
        await self.db.commit()
        return "paid"

    async def fail(self, order_id: str) -> str:
        found = await self._pending_payment(order_id)
        if found is None or found[0].status != PaymentStatus.PENDING:
            await self.db.commit()
            return "ignored"
        found[0].status = PaymentStatus.FAILED
        await self.db.commit()
        return "failed"

    async def _invoice_of(self, payment: Payment) -> Invoice:
        return (await self.db.execute(select(Invoice).where(Invoice.id == payment.invoice_id))).scalar_one()
