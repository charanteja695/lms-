"""Invoices (docs/PRODUCT.md §5.10): drafted by the system, edited by a billing admin, issued (numbered, taxed, frozen), paid, corrected only by credit
notes. Every change to an invoice takes a row lock on it first."""

from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import tax
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import InvoiceKind, InvoiceStatus, PlanStatus
from app.models.billing import BillingProfile, CreditNote, Invoice, InvoiceLine, NumberCounter, OrgPlan
from app.permissions.policy import can_manage_billing, owns
from app.services.outbox import write_event


def _iso(value: Any) -> str | None:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ") if value else None


class InvoiceService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    # ------------------------------------------------------------------ lookup
    async def get(self, public_id: int) -> Invoice:
        invoice = (await self.db.execute(select(Invoice).where(Invoice.public_id == public_id))).scalar_one_or_none()
        if invoice is None:
            raise NotFoundError("Invoice not found.", code="INVOICE_NOT_FOUND")
        return invoice

    async def get_visible(self, auth: AccessTokenClaims, public_id: int) -> Invoice:
        """An organisation's own invoice, or any invoice for a billing admin. A draft is internal until it is issued: the customer never sees it."""
        invoice = await self.get(public_id)
        if not owns(auth, invoice.org_id) or (invoice.status == InvoiceStatus.DRAFT and not can_manage_billing(auth)):
            raise NotFoundError("Invoice not found.", code="INVOICE_NOT_FOUND")
        return invoice

    async def locked(self, invoice: Invoice) -> Invoice:
        return (await self.db.execute(select(Invoice).where(Invoice.id == invoice.id).with_for_update().execution_options(populate_existing=True))).scalar_one()

    async def lines(self, invoice: Invoice) -> list[InvoiceLine]:
        return list((await self.db.execute(select(InvoiceLine).where(InvoiceLine.invoice_id == invoice.id).order_by(InvoiceLine.position))).scalars())

    async def credit_notes(self, invoice: Invoice) -> list[CreditNote]:
        return list((await self.db.execute(select(CreditNote).where(CreditNote.invoice_id == invoice.id).order_by(CreditNote.created_at))).scalars())

    async def profile(self, org_id: int) -> BillingProfile | None:
        return await self.db.get(BillingProfile, org_id)

    async def list_invoices(self, auth: AccessTokenClaims, *, org_id: int | None, status: str | None, page: int, per_page: int) -> tuple[list[Invoice], int]:
        stmt = select(Invoice)
        if can_manage_billing(auth):
            if org_id is not None:
                stmt = stmt.where(Invoice.org_id == org_id)
        else:
            stmt = stmt.where(Invoice.org_id == auth.organization_id, Invoice.status != InvoiceStatus.DRAFT)
        if status:
            stmt = stmt.where(Invoice.status == status)
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows: Any = (await self.db.execute(stmt.order_by(Invoice.created_at.desc(), Invoice.id).limit(per_page).offset((page - 1) * per_page))).scalars()
        return list(rows), total

    # ------------------------------------------------------------------ arithmetic
    def _recalculate(self, invoice: Invoice, lines: list[InvoiceLine], state: str | None) -> None:
        """Totals from the lines. Tax is computed only when the customer's state is known (a draft without a billing profile shows none yet)."""
        invoice.subtotal = sum(line.amount for line in lines)
        invoice.discount, invoice.taxable = tax.after_discount(invoice.subtotal, invoice.discount)
        if state is None:
            invoice.cgst = invoice.sgst = invoice.igst = 0
        else:
            invoice.cgst, invoice.sgst, invoice.igst = tax.gst(invoice.taxable, self.settings.GST_RATE_PERCENT, intra_state=tax.same_state(self.settings.SELLER_STATE, state))
        invoice.total = invoice.taxable + invoice.cgst + invoice.sgst + invoice.igst

    # ------------------------------------------------------------------ creating
    async def create_draft(
        self, *, org_id: int, kind: InvoiceKind, source_type: str, source_id: str, lines: list[dict[str, Any]], discount: int = 0, quote_id: Any = None, note: str | None = None,
    ) -> Invoice | None:
        """A system-generated draft. Idempotent per source: a second call for the same subscription/plan returns None and changes nothing."""
        existing = (await self.db.execute(select(Invoice.id).where(Invoice.source_type == source_type, Invoice.source_id == source_id))).first()
        if existing is not None:
            return None
        invoice = Invoice(
            public_id=new_public_id(), org_id=org_id, kind=kind, source_type=source_type, source_id=source_id, status=InvoiceStatus.DRAFT, quote_id=quote_id, discount=discount, note=note, currency="INR",
        )
        self.db.add(invoice)
        await self.db.flush()
        rows = self._add_lines(invoice, lines)
        profile = await self.profile(org_id)
        self._recalculate(invoice, rows, profile.state if profile else None)
        await self.db.flush()
        return invoice

    def _add_lines(self, invoice: Invoice, lines: list[dict[str, Any]]) -> list[InvoiceLine]:
        rows = [
            InvoiceLine(
                invoice_id=invoice.id, position=index, description=line["description"], sac_code=self.settings.SAC_CODE, quantity=line["quantity"], unit_amount=line["unit_amount"],
                amount=line["quantity"] * line["unit_amount"] if line.get("amount") is None else line["amount"],
            )
            for index, line in enumerate(lines, start=1)
        ]
        self.db.add_all(rows)
        return rows

    async def edit_draft(self, invoice: Invoice, *, lines: list[dict[str, Any]], discount: int, note: str | None) -> Invoice:
        invoice = await self.locked(invoice)
        if invoice.status != InvoiceStatus.DRAFT:
            raise ConflictError("An issued invoice never changes: issue a credit note.", code="INVOICE_NOT_DRAFT")
        for old in await self.lines(invoice):
            await self.db.delete(old)
        await self.db.flush()
        rows = self._add_lines(invoice, lines)
        invoice.discount, invoice.note = discount, note
        profile = await self.profile(invoice.org_id)
        self._recalculate(invoice, rows, profile.state if profile else None)
        await self.db.commit()
        return invoice

    # ------------------------------------------------------------------ numbering
    async def next_number(self, series: str) -> int:
        """The next gap-free number in a series, taken under a row lock so two concurrent issues can never share one."""
        insert = postgresql.insert if self.db.bind is not None and self.db.bind.dialect.name == "postgresql" else sqlite.insert
        await self.db.execute(insert(NumberCounter).values(series=series, last_number=0).on_conflict_do_nothing(index_elements=["series"]))
        counter = (await self.db.execute(select(NumberCounter).where(NumberCounter.series == series).with_for_update().execution_options(populate_existing=True))).scalar_one()
        counter.last_number += 1
        await self.db.flush()
        return counter.last_number

    # ------------------------------------------------------------------ issuing
    async def issue(self, invoice: Invoice) -> Invoice:
        invoice = await self.locked(invoice)
        if invoice.status != InvoiceStatus.DRAFT:
            raise ConflictError(f"This invoice is {invoice.status}.", code="INVOICE_NOT_DRAFT")
        profile = await self.profile(invoice.org_id)
        if profile is None:
            raise ConflictError("The organisation has no billing profile: its legal name and state are needed on a GST invoice.", code="BILLING_PROFILE_MISSING")
        lines = await self.lines(invoice)
        self._recalculate(invoice, lines, profile.state)
        if not lines or invoice.total <= 0:
            raise ConflictError("An invoice needs at least one priced line before it is issued.", code="INVOICE_EMPTY")
        today = utcnow().date()
        invoice.number = f"INV/{tax.financial_year(today)}/{await self.next_number(f'INV/{tax.financial_year(today)}'):06d}"
        invoice.issue_date, invoice.due_date, invoice.status = today, today + timedelta(days=self.settings.INVOICE_DUE_DAYS), InvoiceStatus.ISSUED
        invoice.customer = {"legal_name": profile.legal_name, "gstin": profile.gstin, "state": profile.state, "address": profile.address, "email": profile.email}
        invoice.place_of_supply = profile.state
        self._event("invoice.issued", invoice, total_amount=invoice.total, due_date=invoice.due_date.isoformat())
        await self.db.commit()
        return invoice

    def _event(self, event_type: str, invoice: Invoice, **extra: Any) -> None:
        write_event(
            self.db, event_type=event_type, aggregate_type="invoice", aggregate_id=invoice.id,
            payload={
                "invoice_id": str(invoice.public_id), "number": invoice.number, "organization_id": str(invoice.org_id), "kind": invoice.kind, "status": invoice.status, "currency": invoice.currency,
                "occurred_at": _iso(utcnow()), **extra,
            },
        )

    # ------------------------------------------------------------------ voiding
    async def void(self, invoice: Invoice, reason: str) -> Invoice:
        invoice = await self.locked(invoice)
        if invoice.status not in {InvoiceStatus.DRAFT, InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE} or invoice.amount_paid > 0:
            raise ConflictError("Only an unpaid draft or issued invoice can be voided: issue a credit note for anything else.", code="INVOICE_NOT_VOIDABLE")
        invoice.status, invoice.void_reason = InvoiceStatus.VOID, reason
        for plan in (await self.db.execute(select(OrgPlan).where(OrgPlan.invoice_id == invoice.id, OrgPlan.status == PlanStatus.PENDING))).scalars():
            plan.status = PlanStatus.CANCELLED
        if invoice.number:
            self._event("invoice.voided", invoice, reason=reason)
        await self.db.commit()
        return invoice

    # ------------------------------------------------------------------ credit notes
    async def credit(self, auth: AccessTokenClaims, invoice: Invoice, *, taxable: int, reason: str) -> CreditNote:
        """Reduce what is owed on an issued invoice by ``taxable`` (before tax) plus the tax on it, as a new numbered document."""
        invoice = await self.locked(invoice)
        if invoice.status not in {InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE, InvoiceStatus.PAID}:
            raise ConflictError("Only an issued invoice can be credited.", code="INVOICE_NOT_CREDITABLE")
        if taxable <= 0:
            raise ValidationFailedError(details=[{"field": "taxable_amount", "code": "INVALID_AMOUNT", "message": "Credit an amount greater than zero"}])
        already = int((await self.db.execute(select(func.coalesce(func.sum(CreditNote.taxable), 0)).where(CreditNote.invoice_id == invoice.id))).scalar_one())
        if already + taxable > invoice.taxable:
            raise ConflictError("The credit notes would add up to more than the invoice.", code="CREDIT_EXCEEDS_INVOICE")
        cgst, sgst, igst = tax.gst(taxable, self.settings.GST_RATE_PERCENT, intra_state=invoice.igst == 0)
        if already + taxable == invoice.taxable:  # crediting the whole invoice leaves no rounding remainder
            cgst, sgst, igst = invoice.cgst - await self._credited("cgst", invoice), invoice.sgst - await self._credited("sgst", invoice), invoice.igst - await self._credited("igst", invoice)
        total = taxable + cgst + sgst + igst
        year = tax.financial_year(utcnow().date())
        note = CreditNote(
            public_id=new_public_id(), number=f"CN/{year}/{await self.next_number(f'CN/{year}'):06d}", invoice_id=invoice.id, org_id=invoice.org_id, reason=reason, taxable=taxable, cgst=cgst, sgst=sgst,
            igst=igst, total=total, issued_by=auth.user_id,
        )
        self.db.add(note)
        invoice.credited += total
        await self.db.flush()
        write_event(
            self.db, event_type="credit_note.issued", aggregate_type="credit_note", aggregate_id=note.id,
            payload={"credit_note_id": str(note.public_id), "number": note.number, "invoice_id": str(invoice.public_id), "organization_id": str(invoice.org_id), "amount": note.total, "occurred_at": _iso(utcnow())},
        )
        await self.settle(invoice)
        await self.db.commit()
        return note

    async def _credited(self, column: str, invoice: Invoice) -> int:
        col = getattr(CreditNote, column)
        return int((await self.db.execute(select(func.coalesce(func.sum(col), 0)).where(CreditNote.invoice_id == invoice.id))).scalar_one())

    # ------------------------------------------------------------------ settling
    def owed(self, invoice: Invoice) -> int:
        return max(invoice.total - invoice.credited - invoice.amount_paid, 0)

    async def settle(self, invoice: Invoice) -> None:
        """Mark an issued/overdue invoice paid once payments cover what remains after credit notes. The caller holds the invoice lock and commits."""
        if invoice.status in {InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE} and self.owed(invoice) == 0:
            invoice.status = InvoiceStatus.PAID
            self._event("invoice.paid", invoice, total_amount=invoice.amount_paid)
            await self._activate_plan(invoice)

    async def _activate_plan(self, invoice: Invoice) -> None:
        plan = (await self.db.execute(select(OrgPlan).where(OrgPlan.invoice_id == invoice.id, OrgPlan.status == PlanStatus.PENDING))).scalar_one_or_none()
        if plan is None:
            return
        now = utcnow()
        plan.status, plan.starts_at, plan.ends_at = PlanStatus.ACTIVE, now, now + timedelta(days=plan.valid_days)
        write_event(
            self.db, event_type="plan.activated", aggregate_type="org_plan", aggregate_id=plan.id,
            payload={
                "plan_id": str(plan.public_id), "employer_id": str(plan.org_id), "organization_id": str(plan.org_id), "tier": plan.tier, "job_posts": plan.job_posts, "ends_at": _iso(plan.ends_at),
                "occurred_at": _iso(now),
            },
        )

    # ------------------------------------------------------------------ sweeps
    async def flag_overdue(self, *, limit: int = 200) -> int:
        today = utcnow().date()
        rows = list(
            (
                await self.db.execute(
                    select(Invoice).where(Invoice.status == InvoiceStatus.ISSUED, Invoice.due_date < today).limit(limit).with_for_update(skip_locked=True)
                )
            ).scalars()
        )
        for invoice in rows:
            invoice.status = InvoiceStatus.OVERDUE
            self._event("invoice.overdue", invoice, total_amount=self.owed(invoice))
        await self.db.commit()
        return len(rows)

