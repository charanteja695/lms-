"""Turn rows into response objects, so every endpoint shows an invoice the same way."""

from app.core.config import Settings
from app.models.billing import CreditNote, Invoice, InvoiceLine, Payment
from app.schemas.billing import CreditNoteOut, InvoiceDetail, InvoiceLineOut, InvoiceOut, PaymentOut


def seller(settings: Settings) -> dict[str, str]:
    return {"legal_name": settings.SELLER_LEGAL_NAME, "gstin": settings.SELLER_GSTIN, "state": settings.SELLER_STATE}


def invoice_out(invoice: Invoice, settings: Settings) -> InvoiceOut:
    payable = invoice.total - invoice.credited
    return InvoiceOut(
        invoice_id=invoice.public_id, number=invoice.number, organization_id=invoice.org_id, kind=invoice.kind, status=invoice.status, currency=invoice.currency, subtotal=invoice.subtotal,
        discount=invoice.discount, taxable=invoice.taxable, cgst=invoice.cgst, sgst=invoice.sgst, igst=invoice.igst, total=invoice.total, amount_paid=invoice.amount_paid, credited=invoice.credited,
        balance_due=max(payable - invoice.amount_paid, 0) if invoice.number and invoice.status != "void" else 0, refund_due=max(invoice.amount_paid - payable, 0),
        issue_date=invoice.issue_date, due_date=invoice.due_date, place_of_supply=invoice.place_of_supply, customer=invoice.customer, seller=seller(settings), note=invoice.note,
        void_reason=invoice.void_reason, created_at=invoice.created_at,
    )


def invoice_detail(invoice: Invoice, settings: Settings, lines: list[InvoiceLine], payments: list[Payment], notes: list[CreditNote]) -> InvoiceDetail:
    base = invoice_out(invoice, settings)
    return InvoiceDetail(
        **{name: getattr(base, name) for name in InvoiceOut.model_fields}, lines=[InvoiceLineOut.model_validate(line) for line in lines],
        payments=[PaymentOut.model_validate(payment) for payment in payments], credit_notes=[CreditNoteOut.model_validate(note) for note in notes],
    )
