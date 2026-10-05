"""Money is always an integer number of paise (1/100 rupee): no floats anywhere a total is added up."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, NullableJSONType
from app.domain.enums import InvoiceStatus, PaymentStatus, PlanStatus, QuoteStatus


class PriceItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The price list: what a course seat costs per 365 days, or what an employer plan costs."""

    __tablename__ = "price_items"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    kind: Mapped[str] = mapped_column(String(14))
    code: Mapped[str] = mapped_column(String(60))  # a course id (course_seat) or a tier name (employer_plan)
    name: Mapped[str] = mapped_column(String(160))
    unit_amount: Mapped[int] = mapped_column(BigInteger)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)  # employer_plan: {job_posts, valid_days}
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (UniqueConstraint("kind", "code", name="uq_price_items_kind_code"),)


class BillingProfile(TimestampMixin, Base):
    """What an invoice to an organisation needs and user-management does not carry: legal name, GSTIN and the state that decides
    CGST+SGST versus IGST. Set by the organisation's own head/admin or by a billing admin."""

    __tablename__ = "billing_profiles"

    org_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    legal_name: Mapped[str] = mapped_column(String(200))
    gstin: Mapped[str | None] = mapped_column(String(15))
    state: Mapped[str] = mapped_column(String(60))
    address: Mapped[str] = mapped_column(String(500))
    email: Mapped[str | None] = mapped_column(String(200))
    updated_by: Mapped[int] = mapped_column(BigInteger)


class Quote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "quotes"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    org_id: Mapped[int] = mapped_column(BigInteger)
    requested_by: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(10), default=QuoteStatus.OPEN)
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONType)  # [{course_id, name, seats, term_days, unit_amount, amount}]
    subtotal: Mapped[int] = mapped_column(BigInteger)
    discount: Mapped[int] = mapped_column(BigInteger, default=0)
    discount_note: Mapped[str | None] = mapped_column(String(300))
    gst: Mapped[int] = mapped_column(BigInteger)
    total: Mapped[int] = mapped_column(BigInteger)
    valid_until: Mapped[datetime]
    accepted_at: Mapped[datetime | None]
    used_at: Mapped[datetime | None]  # set when a subscription's invoice took its price

    __table_args__ = (Index("ix_quotes_org_status", "org_id", "status"),)


class Invoice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "invoices"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    number: Mapped[str | None] = mapped_column(String(30), unique=True)  # assigned when issued, gap-free per financial year
    org_id: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(12))
    source_type: Mapped[str] = mapped_column(String(20))  # subscription | plan
    source_id: Mapped[str] = mapped_column(String(40))  # the subscription's or plan purchase's public id
    status: Mapped[str] = mapped_column(String(8), default=InvoiceStatus.DRAFT)
    quote_id: Mapped[Any | None] = mapped_column(ForeignKey("quotes.id", ondelete="SET NULL"))
    subtotal: Mapped[int] = mapped_column(BigInteger, default=0)
    discount: Mapped[int] = mapped_column(BigInteger, default=0)
    taxable: Mapped[int] = mapped_column(BigInteger, default=0)
    cgst: Mapped[int] = mapped_column(BigInteger, default=0)
    sgst: Mapped[int] = mapped_column(BigInteger, default=0)
    igst: Mapped[int] = mapped_column(BigInteger, default=0)
    total: Mapped[int] = mapped_column(BigInteger, default=0)
    amount_paid: Mapped[int] = mapped_column(BigInteger, default=0)
    credited: Mapped[int] = mapped_column(BigInteger, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    customer: Mapped[dict[str, Any] | None] = mapped_column(NullableJSONType)  # snapshot of the billing profile at issue
    place_of_supply: Mapped[str | None] = mapped_column(String(60))
    issue_date: Mapped[date | None]
    due_date: Mapped[date | None]
    note: Mapped[str | None] = mapped_column(String(500))  # e.g. "No price configured for course X"
    void_reason: Mapped[str | None] = mapped_column(String(300))

    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_invoices_source"),
        Index("ix_invoices_org_status", "org_id", "status"),
        Index("ix_invoices_status_due", "status", "due_date"),
    )


class InvoiceLine(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "invoice_lines"

    invoice_id: Mapped[Any] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(300))
    sac_code: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_amount: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (Index("ix_invoice_lines_invoice", "invoice_id", "position"),)


class NumberCounter(Base):
    """Gap-free document numbers: one row per series and financial year, locked FOR UPDATE while a number is taken."""

    __tablename__ = "number_counters"

    series: Mapped[str] = mapped_column(String(20), primary_key=True)  # e.g. "INV/2026-27", "CN/2026-27"
    last_number: Mapped[int] = mapped_column(Integer, default=0)


class Payment(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "payments"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    invoice_id: Mapped[Any] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    method: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(10), default=PaymentStatus.PENDING)
    amount: Mapped[int] = mapped_column(BigInteger)
    reference: Mapped[str | None] = mapped_column(String(120))  # cheque/UTR/UPI reference for a manual payment
    gateway_order_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(80), unique=True)
    recorded_by: Mapped[int | None] = mapped_column(BigInteger)
    paid_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_payments_invoice", "invoice_id"),)


class GatewayEvent(Base):
    """De-duplication for the payment gateway's webhook: it may deliver the same event more than once."""

    __tablename__ = "gateway_events"

    event_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    received_at: Mapped[datetime]


class CreditNote(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A correction to an issued invoice: a new signed document, never an edit of the original."""

    __tablename__ = "credit_notes"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    invoice_id: Mapped[Any] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    org_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(300))
    taxable: Mapped[int] = mapped_column(BigInteger)
    cgst: Mapped[int] = mapped_column(BigInteger, default=0)
    sgst: Mapped[int] = mapped_column(BigInteger, default=0)
    igst: Mapped[int] = mapped_column(BigInteger, default=0)
    total: Mapped[int] = mapped_column(BigInteger)
    issued_by: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (Index("ix_credit_notes_invoice", "invoice_id"),)


class OrgPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An employer's purchased plan. Billing only records the entitlement and announces it (`plan.activated`/`plan.expired`);
    whether a job may be posted is job-portal-service's decision, from the event."""

    __tablename__ = "org_plans"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    org_id: Mapped[int] = mapped_column(BigInteger)
    tier: Mapped[str] = mapped_column(String(60))
    job_posts: Mapped[int] = mapped_column(Integer)
    valid_days: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default=PlanStatus.PENDING)
    invoice_id: Mapped[Any] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"))
    starts_at: Mapped[datetime | None]
    ends_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_org_plans_org_status", "org_id", "status"), Index("ix_org_plans_status_end", "status", "ends_at"))

