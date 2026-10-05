"""Request and response shapes. Every amount is an integer number of paise (1/100 rupee)."""

from datetime import date
from typing import Annotated, Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from app.domain.enums import PriceKind
from app.schemas.types import PublicIdOut, Timestamp, id_field, text

Paise = Annotated[int, Field(ge=0, le=100_000_000_000)]
CourseId = id_field("Course", "1755000000001001")


# ---------------------------------------------------------------- billing profile
class BillingProfileIn(RequestSchema):
    legal_name: text(200, min_length=2)  # type: ignore[valid-type]
    gstin: text(15, min_length=15) | None = Field(default=None, description="Optional (an unregistered customer has none); checked for shape only")  # type: ignore[valid-type]
    state: text(60, min_length=2)  # type: ignore[valid-type]
    address: text(500, min_length=5)  # type: ignore[valid-type]
    email: text(200, min_length=3) | None = None  # type: ignore[valid-type]


class BillingProfileOut(ResponseSchema):
    organization_id: PublicIdOut = Field(validation_alias="org_id")
    legal_name: str
    gstin: str | None
    state: str
    address: str
    email: str | None
    updated_at: Timestamp


class BillingProfileResponse(SuccessResponse):
    profile: BillingProfileOut


# ---------------------------------------------------------------- prices
class PriceCreate(RequestSchema):
    kind: PriceKind
    code: text(60, min_length=1)  # type: ignore[valid-type]
    name: text(160, min_length=2)  # type: ignore[valid-type]
    unit_amount: Paise
    job_posts: int | None = Field(default=None, ge=1, le=10_000, description="employer_plan only")
    valid_days: int | None = Field(default=None, ge=1, le=1_095, description="employer_plan only")

    @model_validator(mode="after")
    def _plan_fields(self) -> "PriceCreate":
        if self.kind == PriceKind.EMPLOYER_PLAN and (self.job_posts is None or self.valid_days is None):
            raise PydanticCustomError("REQUIRED", "An employer plan needs job_posts and valid_days")
        if self.kind == PriceKind.COURSE_SEAT and (self.job_posts is not None or self.valid_days is not None):
            raise PydanticCustomError("NOT_ALLOWED", "job_posts and valid_days apply to an employer plan only")
        return self


class PriceUpdate(RequestSchema):
    name: text(160, min_length=2) | None = None  # type: ignore[valid-type]
    unit_amount: Paise | None = None
    active: bool | None = None


class PriceOut(ResponseSchema):
    price_id: PublicIdOut = Field(validation_alias="public_id")
    kind: str
    code: str
    name: str
    unit_amount: int
    meta: dict[str, Any]
    active: bool


class PriceResponse(SuccessResponse):
    price: PriceOut


class PricePage(SuccessResponse):
    prices: list[PriceOut]
    page_context: PageContext


# ---------------------------------------------------------------- quotes
class QuoteLineIn(RequestSchema):
    course_id: CourseId  # type: ignore[valid-type]
    seats: int = Field(ge=1, le=100_000)
    term_days: int = Field(ge=1, le=1_095)


class QuoteCreate(RequestSchema):
    organization_id: id_field("Organisation", "1755000000007003") | None = Field(default=None, description="Billing managers name the organisation; everyone else's is their own")  # type: ignore[valid-type]
    lines: Annotated[list[QuoteLineIn], Field(min_length=1, max_length=20)]


class DiscountIn(RequestSchema):
    amount: Paise
    note: text(300, min_length=3)  # type: ignore[valid-type]


class QuoteLineOut(ResponseSchema):
    course_id: str
    name: str
    seats: int
    term_days: int
    unit_amount: int
    amount: int


class QuoteOut(ResponseSchema):
    quote_id: PublicIdOut = Field(validation_alias="public_id")
    organization_id: PublicIdOut = Field(validation_alias="org_id")
    status: str
    lines: list[QuoteLineOut]
    subtotal: int
    discount: int
    discount_note: str | None
    gst: int
    total: int
    valid_until: Timestamp
    accepted_at: Timestamp | None
    created_at: Timestamp


class QuoteResponse(SuccessResponse):
    quote: QuoteOut


class QuotePage(SuccessResponse):
    quotes: list[QuoteOut]
    page_context: PageContext


# ---------------------------------------------------------------- invoices
class InvoiceLineIn(RequestSchema):
    description: text(300, min_length=3)  # type: ignore[valid-type]
    quantity: int = Field(default=1, ge=1, le=1_000_000)
    unit_amount: Paise


class InvoiceEdit(RequestSchema):
    """Replaces a draft's lines. An issued invoice cannot be edited: credit it."""

    lines: Annotated[list[InvoiceLineIn], Field(min_length=1, max_length=50)]
    discount: Paise = 0
    note: text(500) | None = None  # type: ignore[valid-type]


class VoidIn(RequestSchema):
    reason: text(300, min_length=3)  # type: ignore[valid-type]


class InvoiceLineOut(ResponseSchema):
    position: int
    description: str
    sac_code: str
    quantity: int
    unit_amount: int
    amount: int


class PaymentOut(ResponseSchema):
    payment_id: PublicIdOut = Field(validation_alias="public_id")
    method: str
    status: str
    amount: int
    reference: str | None
    gateway_order_id: str | None
    paid_at: Timestamp | None
    created_at: Timestamp


class CreditNoteOut(ResponseSchema):
    credit_note_id: PublicIdOut = Field(validation_alias="public_id")
    number: str
    reason: str
    taxable: int
    cgst: int
    sgst: int
    igst: int
    total: int
    created_at: Timestamp


class InvoiceOut(ResponseSchema):
    invoice_id: PublicIdOut
    number: str | None
    organization_id: PublicIdOut
    kind: str
    status: str
    currency: str
    subtotal: int
    discount: int
    taxable: int
    cgst: int
    sgst: int
    igst: int
    total: int
    amount_paid: int
    credited: int
    balance_due: int
    refund_due: int
    issue_date: date | None
    due_date: date | None
    place_of_supply: str | None
    customer: dict[str, Any] | None
    seller: dict[str, str]
    note: str | None
    void_reason: str | None
    created_at: Timestamp


class InvoiceDetail(InvoiceOut):
    lines: list[InvoiceLineOut]
    payments: list[PaymentOut]
    credit_notes: list[CreditNoteOut]


class InvoiceResponse(SuccessResponse):
    invoice: InvoiceDetail


class InvoicePage(SuccessResponse):
    invoices: list[InvoiceOut]
    page_context: PageContext


# ---------------------------------------------------------------- payments and credit notes
class ManualPaymentIn(RequestSchema):
    amount: Paise = Field(gt=0)
    reference: text(100, min_length=2)  # type: ignore[valid-type]
    method: text(30) | None = Field(default=None, description="bank transfer, cheque, UPI...: noted with the reference")  # type: ignore[valid-type]


class GatewayPaymentIn(RequestSchema):
    amount: Paise | None = Field(default=None, description="Default: everything still owed")


class GatewayPaymentOut(ResponseSchema):
    payment_id: PublicIdOut
    order_id: str
    amount: int
    currency: str


class PaymentResponse(SuccessResponse):
    payment: PaymentOut


class GatewayPaymentResponse(SuccessResponse):
    gateway_payment: GatewayPaymentOut


class CreditNoteIn(RequestSchema):
    taxable_amount: Paise = Field(gt=0, description="The amount to credit before tax; the tax on it is added")
    reason: text(300, min_length=3)  # type: ignore[valid-type]


class CreditNoteResponse(SuccessResponse):
    credit_note: CreditNoteOut


class WebhookResponse(ResponseSchema):
    status: str
    result: str


# ---------------------------------------------------------------- employer plans
class PlanTierOut(ResponseSchema):
    tier: str
    name: str
    price: int
    job_posts: int
    valid_days: int


class PlanTierPage(SuccessResponse):
    tiers: list[PlanTierOut]


class OrgPlanOut(ResponseSchema):
    plan_id: PublicIdOut = Field(validation_alias="public_id")
    tier: str
    job_posts: int
    valid_days: int
    status: str
    starts_at: Timestamp | None
    ends_at: Timestamp | None


class PurchaseResponse(SuccessResponse):
    plan: OrgPlanOut
    invoice: InvoiceOut


class OrgPlanPage(SuccessResponse):
    plans: list[OrgPlanOut]
