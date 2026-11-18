"""Schemas for Institutional Course Purchases, Dynamic Pricing, Quotations, and Package Licensing."""

from datetime import datetime
from typing import Any

from lms_common.envelopes import PageContext, SuccessResponse
from pydantic import BaseModel, Field


class RequestedCourseItem(BaseModel):
    course_id: int
    course_title: str
    course_slug: str | None = None


class QuotationCoursePriceItem(BaseModel):
    course_id: int
    course_title: str
    pricing_method: str = "fixed"  # fixed | monthly | hourly
    unit_price_paise: int
    rate_label: str | None = None
    students: int | None = None
    duration_days: int | None = None
    billable_units: float | int | None = None
    subtotal_paise: int | None = None


class QuotationData(BaseModel):
    quotation_number: str | None = None
    version: int = 1
    course_prices: list[QuotationCoursePriceItem]
    subtotal_paise: int
    discount_percent: int = 0
    discount_paise: int = 0
    discount_note: str | None = None
    taxable_paise: int | None = None
    tax_rate_percent: int = 18
    tax_paise: int = 0
    total_paise: int
    approved_seats: int
    approved_duration_days: int
    package_starts_at: str | None = None
    package_ends_at: str | None = None
    notes: str | None = None
    quoted_at: str | None = None
    expires_at: str | None = None


class PaymentInfoData(BaseModel):
    transaction_id: str
    gateway_order_id: str | None = None
    gateway_payment_id: str | None = None
    amount_paid_paise: int
    method: str
    paid_at: str
    verified: bool = True


class BulkDiscountTier(BaseModel):
    min_students: int = Field(ge=1)
    max_students: int | None = None
    discount_percent: int = Field(default=0, ge=0, le=100)
    fixed_discount_paise: int = Field(default=0, ge=0)


class CoursePricingIn(BaseModel):
    individual_price_paise: int = Field(default=199900, ge=0)
    pricing_method: str = Field(default="fixed")  # fixed | monthly | hourly
    fixed_price_paise: int = Field(default=30000, ge=0)
    monthly_price_paise: int = Field(default=10000, ge=0)
    monthly_billing_rule: str = Field(default="pro_rata")  # pro_rata | round_up
    hourly_price_paise: int = Field(default=1000, ge=0)
    billable_hours: int = Field(default=40, ge=1)
    bulk_discount_tiers: list[BulkDiscountTier] = Field(default_factory=list)
    gst_percent: int = Field(default=18, ge=0, le=100)
    min_students: int = Field(default=1, ge=1)
    max_students: int = Field(default=50000, ge=1)
    min_duration_days: int = Field(default=7, ge=1)
    max_duration_days: int = Field(default=1825, ge=1)
    effective_from: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool = True
    # Discount, metadata and admin fields
    course_title: str | None = None
    course_code: str | None = None
    category: str | None = None
    original_price_paise: int | None = None
    discount_paise: int | None = None
    discount_type: str | None = "none"
    discount_percent: int | None = 0
    discount_value: int | None = 0
    valid_days: int | None = None
    reason: str | None = None
    admin_name: str | None = None
    admin_role: str | None = None
    price_paise: int | None = None


class CoursePricingAuditOut(BaseModel):
    id: str
    public_id: int
    course_id: int
    course_title: str
    course_code: str | None = None
    previous_individual_price_paise: int
    new_individual_price_paise: int
    previous_institutional_price_paise: int
    new_institutional_price_paise: int
    pricing_method: str
    gst_percent: int
    admin_user_id: int
    admin_email: str
    admin_name: str | None = None
    admin_role: str | None = None
    reason: str | None = None
    effective_from: datetime | None = None
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class CoursePricingAuditListResponse(SuccessResponse):
    message: str = "Price change history retrieved successfully"
    course_id: int | None = None
    total: int = 0
    page: int = 1
    per_page: int = 20
    audits: list[CoursePricingAuditOut] = Field(default_factory=list)


class CoursePricingOut(BaseModel):
    course_id: int
    course_title: str
    course_code: str | None = None
    category: str = "Technology"
    slug: str | None = None
    individual_price_paise: int
    pricing_method: str = "fixed"
    fixed_price_paise: int = 30000
    monthly_price_paise: int = 10000
    monthly_billing_rule: str = "pro_rata"
    hourly_price_paise: int = 1000
    billable_hours: int = 40
    bulk_discount_tiers: list[BulkDiscountTier] = Field(default_factory=list)
    gst_percent: int = 18
    min_students: int = 1
    max_students: int = 50000
    min_duration_days: int = 7
    max_duration_days: int = 1825
    effective_from: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool = True
    is_published: bool = True
    # Discount and display fields
    original_price_paise: int | None = None
    discount_paise: int = 0
    discount_type: str = "none"
    discount_percent: int = 0
    discount_value: int = 0
    valid_days: int = 180
    last_updated_at: datetime | None = None
    last_updated_by: str | None = None
    # backward-compat fields
    price_paise: int = 199900
    institutional_price_per_seat_paise: int = 30000
    default_duration_days: int = 180


class CoursePricingSummaryResponse(SuccessResponse):
    message: str = "Course pricing summary retrieved"
    total_courses: int = 0
    individual_updates: int = 0
    institutional_updates: int = 0
    active_discounts: int = 0


class CoursePricingListResponse(SuccessResponse):
    course_pricing: list[CoursePricingOut]
    items: list[CoursePricingOut] = Field(default_factory=list)


# ----------------------------------------------------------------------
# Calculator schemas
# ----------------------------------------------------------------------

class PurchaseCalculationIn(BaseModel):
    course_ids: list[int] = Field(min_length=1)
    students: int = Field(ge=1, le=100000)
    starts_at: datetime
    ends_at: datetime


class CourseCalculationItem(BaseModel):
    course_id: int
    course_title: str
    pricing_method: str
    rate_paise: int
    rate_label: str
    students: int
    duration_days: int
    duration_label: str
    billable_units: float | int
    subtotal_paise: int


class PurchaseCalculationOut(BaseModel):
    course_breakdown: list[CourseCalculationItem]
    total_students: int
    total_duration_days: int
    total_duration_months: float
    starts_at: datetime
    ends_at: datetime
    subtotal_paise: int
    bulk_discount_percent: int
    bulk_discount_paise: int
    bulk_discount_note: str
    taxable_paise: int
    gst_percent: int
    gst_paise: int
    grand_total_paise: int


class PurchaseCalculationResponse(SuccessResponse):
    calculation: PurchaseCalculationOut


# ----------------------------------------------------------------------
# Request & Quotation schemas
# ----------------------------------------------------------------------

class InstitutionalRequestCreateIn(BaseModel):
    contact_person: str = Field(min_length=1, max_length=255)
    contact_email: str = Field(min_length=3, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=50)
    requested_courses: list[RequestedCourseItem] = Field(min_length=1)
    seats_requested: int = Field(ge=1, le=100000)
    duration_days_requested: int = Field(default=180, ge=1, le=3650)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    message: str | None = None


class QuotationCreateIn(BaseModel):
    course_prices: list[QuotationCoursePriceItem] = Field(min_length=1)
    subtotal_paise: int = Field(ge=0)
    discount_paise: int = Field(default=0, ge=0)
    discount_note: str | None = None
    tax_rate_percent: int = Field(default=18, ge=0, le=100)
    tax_paise: int = Field(default=0, ge=0)
    total_paise: int = Field(ge=0)
    approved_seats: int = Field(ge=1, le=100000)
    approved_duration_days: int = Field(default=180, ge=1, le=3650)
    package_starts_at: datetime | None = None
    package_ends_at: datetime | None = None
    notes: str | None = None
    valid_days: int = Field(default=14, ge=1, le=365)


class ModificationRequestIn(BaseModel):
    notes: str = Field(min_length=1)


class RejectRequestIn(BaseModel):
    reason: str | None = None


class PaymentVerificationIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class TestPaymentIn(BaseModel):
    payment_method: str = "test_gateway"


class InstitutionalRequestOut(BaseModel):
    public_id: str
    organization_id: str
    institution_name: str
    institution_code: str | None = None
    contact_person: str
    contact_email: str
    contact_phone: str | None = None
    requested_courses: list[RequestedCourseItem]
    seats_requested: int
    duration_days_requested: int
    starts_at_requested: datetime | None = None
    ends_at_requested: datetime | None = None
    calculation_breakdown: PurchaseCalculationOut | None = None
    quotation_versions: list[dict[str, Any]] = Field(default_factory=list)
    message: str | None = None
    status: str
    quotation: QuotationData | None = None
    quoted_by: str | None = None
    modification_notes: str | None = None
    payment_info: PaymentInfoData | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    package_starts_at: datetime | None = None
    package_ends_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class InstitutionalRequestResponse(SuccessResponse):
    request: InstitutionalRequestOut


class InstitutionalRequestListResponse(SuccessResponse):
    requests: list[InstitutionalRequestOut]
    items: list[InstitutionalRequestOut] = Field(default_factory=list)
    page_context: PageContext


class InstitutionalCheckoutResponse(SuccessResponse):
    provider: str
    key_id: str | None
    order_id: str
    amount: int
    currency: str
    seller_name: str
    request_id: str


class StudentSeatUsageItem(BaseModel):
    student_user_id: str
    student_name: str
    student_email: str
    course_id: str
    course_title: str
    enrolled_at: str | None = None


class InstitutionalPackageOut(BaseModel):
    request_id: str
    organization_id: str
    institution_name: str
    institution_code: str | None = None
    purchased_courses: list[RequestedCourseItem]
    courses: list[RequestedCourseItem] = Field(default_factory=list)
    seats_total: int
    seats_used: int
    seats_available: int
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    total_paid_paise: int
    status: str
    students_using: list[StudentSeatUsageItem] = Field(default_factory=list)


class InstitutionalPackageListResponse(SuccessResponse):
    packages: list[InstitutionalPackageOut]
    items: list[InstitutionalPackageOut] = Field(default_factory=list)


class InstitutionalPackageResponse(SuccessResponse):
    package: InstitutionalPackageOut


class RevenueReportItem(BaseModel):
    request_id: str
    institution_name: str
    organization_id: str
    transaction_id: str
    amount_paid_paise: int
    courses_count: int
    courses_summary: str
    seats_purchased: int
    paid_at: str
    approved_at: str | None = None


class InstitutionalRevenueReportResponse(SuccessResponse):
    total_revenue_paise: int
    total_transactions: int
    total_seats_licensed: int
    transactions: list[RevenueReportItem]
