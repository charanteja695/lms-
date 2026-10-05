"""Invoices: an organisation reads and pays its own; a billing manager edits drafts, issues, voids, records manual payments and issues credit notes."""

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    DbSession,
    InvoiceIdParam,
    PaymentGatewayDep,
    RequireBillingAdmin,
    RequireBillingContact,
    SettingsDep,
    WriteRateLimit,
)
from app.api.presenters import invoice_detail, invoice_out
from app.api.responses import AUTHENTICATED, errors
from app.core.config import Settings
from app.core.exceptions import ValidationFailedError
from app.core.ids import parse_public_id
from app.domain.enums import InvoiceStatus
from app.models.billing import Invoice
from app.permissions.policy import can_manage_billing
from app.schemas.billing import (
    CreditNoteIn,
    CreditNoteOut,
    CreditNoteResponse,
    GatewayPaymentIn,
    GatewayPaymentOut,
    GatewayPaymentResponse,
    InvoiceEdit,
    InvoicePage,
    InvoiceResponse,
    ManualPaymentIn,
    PaymentOut,
    PaymentResponse,
    VoidIn,
)
from app.services.invoice_service import InvoiceService
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/invoices", tags=["Invoices"])
admin = APIRouter(prefix="/admin/invoices", tags=["Invoices (admin)"])


async def _detail(service: InvoiceService, payments: PaymentService, invoice: Invoice, settings: Settings, message: str = "") -> InvoiceResponse:
    return InvoiceResponse(message=message, invoice=invoice_detail(invoice, settings, await service.lines(invoice), await payments.list_for_invoice(invoice), await service.credit_notes(invoice)))


@router.get("", response_model=InvoicePage, summary="Invoices", responses=errors(*AUTHENTICATED),
            description="An organisation sees its own issued invoices; a billing manager sees everyone's, drafts included (`organization_id`, `status` filter).")
async def list_invoices(
    auth: RequireBillingContact, db: DbSession, settings: SettingsDep, status: Annotated[InvoiceStatus | None, Query()] = None, organization_id: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> InvoicePage:
    org = parse_public_id(organization_id) if organization_id and can_manage_billing(auth) else None
    invoices, total = await InvoiceService(db, settings).list_invoices(auth, org_id=org, status=status.value if status else None, page=page, per_page=per_page)
    return InvoicePage(
        message="", invoices=[invoice_out(i, settings) for i in invoices],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse, summary="An invoice", responses=errors(*AUTHENTICATED, 404))
async def get_invoice(invoice_id: InvoiceIdParam, auth: RequireBillingContact, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> InvoiceResponse:
    service = InvoiceService(db, settings)
    return await _detail(service, PaymentService(db, settings, gateway), await service.get_visible(auth, invoice_id), settings)


@router.post(
    "/{invoice_id}/payments/gateway", response_model=GatewayPaymentResponse, status_code=201, summary="Start an online payment", responses=errors(*AUTHENTICATED, 404, 409, 503),
    description="Creates an order with the payment provider. A contract only (D13): `503 PAYMENT_GATEWAY_NOT_CONFIGURED` until a provider is wired — pay by bank transfer and ask the "
    "platform team to record it.", dependencies=[WriteRateLimit],
)
async def pay_online(invoice_id: InvoiceIdParam, body: GatewayPaymentIn, auth: RequireBillingContact, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> GatewayPaymentResponse:
    invoice = await InvoiceService(db, settings).get_visible(auth, invoice_id)
    payment, order_id = await PaymentService(db, settings, gateway).start_gateway_payment(invoice, amount=body.amount)
    return GatewayPaymentResponse(message="Complete the payment with the provider.", gateway_payment=GatewayPaymentOut(payment_id=payment.public_id, order_id=order_id, amount=payment.amount, currency=invoice.currency))


@admin.put("/{invoice_id}", response_model=InvoiceResponse, summary="Edit a draft", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit],
           description="Replaces the lines, discount and note of a draft. An issued invoice never changes.")
async def edit_draft(invoice_id: InvoiceIdParam, body: InvoiceEdit, auth: RequireBillingAdmin, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> InvoiceResponse:
    service = InvoiceService(db, settings)
    invoice = await service.edit_draft(
        await service.get(invoice_id), lines=[{"description": line.description, "quantity": line.quantity, "unit_amount": line.unit_amount} for line in body.lines], discount=body.discount, note=body.note,
    )
    return await _detail(service, PaymentService(db, settings, gateway), invoice, settings, "Saved.")


@admin.post("/{invoice_id}/issue", response_model=InvoiceResponse, summary="Issue a draft", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit],
            description="Numbers it (gap-free per financial year), freezes the customer's details and the tax split, and makes it payable.")
async def issue_invoice(invoice_id: InvoiceIdParam, auth: RequireBillingAdmin, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> InvoiceResponse:
    service = InvoiceService(db, settings)
    return await _detail(service, PaymentService(db, settings, gateway), await service.issue(await service.get(invoice_id)), settings, "Issued.")


@admin.post("/{invoice_id}/void", response_model=InvoiceResponse, summary="Void an unpaid invoice", responses=errors(*AUTHENTICATED, 404, 409), dependencies=[WriteRateLimit])
async def void_invoice(invoice_id: InvoiceIdParam, body: VoidIn, auth: RequireBillingAdmin, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> InvoiceResponse:
    service = InvoiceService(db, settings)
    return await _detail(service, PaymentService(db, settings, gateway), await service.void(await service.get(invoice_id), body.reason), settings, "Voided.")


@admin.post("/{invoice_id}/payments/manual", response_model=PaymentResponse, status_code=201, summary="Record money received outside the platform", responses=errors(*AUTHENTICATED, 404, 409),
            dependencies=[WriteRateLimit], description="Bank transfer, cheque, UPI reference. Always available, gateway or not. A part payment is allowed.")
async def record_manual_payment(invoice_id: InvoiceIdParam, body: ManualPaymentIn, auth: RequireBillingAdmin, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> PaymentResponse:
    invoice = await InvoiceService(db, settings).get(invoice_id)
    payment = await PaymentService(db, settings, gateway).record_manual(auth, invoice, amount=body.amount, reference=body.reference, method_note=body.method)
    return PaymentResponse(message="Recorded.", payment=PaymentOut.model_validate(payment))


@admin.post("/{invoice_id}/credit-notes", response_model=CreditNoteResponse, status_code=201, summary="Issue a credit note", responses=errors(*AUTHENTICATED, 404, 409, 422), dependencies=[WriteRateLimit],
            description="The correction to an issued invoice: reduces what is owed by the amount plus the tax on it. On a paid invoice it shows up as `refund_due`.")
async def issue_credit_note(invoice_id: InvoiceIdParam, body: CreditNoteIn, auth: RequireBillingAdmin, db: DbSession, settings: SettingsDep) -> CreditNoteResponse:
    service = InvoiceService(db, settings)
    if body.taxable_amount <= 0:
        raise ValidationFailedError(details=[{"field": "taxable_amount", "code": "INVALID_AMOUNT", "message": "Credit an amount greater than zero"}])
    note = await service.credit(auth, await service.get(invoice_id), taxable=body.taxable_amount, reason=body.reason)
    return CreditNoteResponse(message="Credit note issued.", credit_note=CreditNoteOut.model_validate(note))
