"""Pydantic schemas for student subscription plans, payment settings, checkout, verification, and payment history."""

from typing import Annotated, Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import BaseModel, Field

from app.schemas.types import PublicIdOut, Timestamp, id_field, text

Paise = Annotated[int, Field(ge=0, le=100_000_000_000)]
CourseIdIn = id_field("course_id", "1755000000001001")


# ---------------------------------------------------------------- admin plans & payment settings
class AssessmentAccessRules(BaseModel):
    chapter_tests: bool = True
    module_tests: bool = False
    final_exam: bool = False
    proctoring: bool = False


class CourseAccessRules(BaseModel):
    all_approved_courses: bool = True
    course_ids: list[str] = Field(default_factory=list)


class SubscriptionPlanCreate(RequestSchema):
    code: text(40, min_length=2)  # type: ignore[valid-type]
    name: text(120, min_length=2)  # type: ignore[valid-type]
    description: str = Field(default="", max_length=500)
    price_paise: Paise
    min_price_paise: Paise | None = None
    max_price_paise: Paise | None = None
    billing_duration_days: int = Field(default=30, ge=1, le=1095)
    billing_label: str = Field(default="month", max_length=40)
    max_courses: int | None = Field(default=None, ge=1, le=10_000)
    features: list[str] = Field(default_factory=list)
    course_access_rules: CourseAccessRules = Field(default_factory=CourseAccessRules)
    assessment_access: AssessmentAccessRules = Field(default_factory=AssessmentAccessRules)
    certificate_level: str = Field(default="basic", pattern="^(none|basic|premium|pro)$")
    support_tier: str = Field(default="Email Support", max_length=80)
    is_active: bool = True
    is_recommended: bool = False
    display_order: int = Field(default=0, ge=0, le=1000)
    tier_rank: int = Field(default=1, ge=1, le=100)


class SubscriptionPlanUpdate(RequestSchema):
    name: text(120, min_length=2) | None = None  # type: ignore[valid-type]
    description: str | None = Field(default=None, max_length=500)
    price_paise: Paise | None = None
    min_price_paise: Paise | None = None
    max_price_paise: Paise | None = None
    billing_duration_days: int | None = Field(default=None, ge=1, le=1095)
    billing_label: str | None = Field(default=None, max_length=40)
    max_courses: int | None = Field(default=None, ge=1, le=10_000)
    clear_max_courses: bool = False
    features: list[str] | None = None
    course_access_rules: CourseAccessRules | None = None
    assessment_access: AssessmentAccessRules | None = None
    certificate_level: str | None = Field(default=None, pattern="^(none|basic|premium|pro)$")
    support_tier: str | None = Field(default=None, max_length=80)
    is_active: bool | None = None
    is_recommended: bool | None = None
    display_order: int | None = Field(default=None, ge=0, le=1000)
    tier_rank: int | None = Field(default=None, ge=1, le=100)


class SubscriptionPlanOut(ResponseSchema):
    plan_id: PublicIdOut = Field(validation_alias="public_id")
    code: str
    name: str
    description: str
    price_paise: int
    min_price_paise: int | None
    max_price_paise: int | None
    billing_duration_days: int
    billing_label: str
    max_courses: int | None
    features: list[str]
    course_access_rules: dict[str, Any]
    assessment_access: dict[str, Any]
    certificate_level: str
    support_tier: str
    is_active: bool
    is_recommended: bool
    display_order: int
    tier_rank: int
    created_at: Timestamp
    updated_at: Timestamp


class SubscriptionPlanResponse(SuccessResponse):
    plan: SubscriptionPlanOut


class SubscriptionPlanListResponse(SuccessResponse):
    plans: list[SubscriptionPlanOut]


class PaymentSettingsIn(RequestSchema):
    payments_enabled: bool
    min_amount_paise: Paise
    max_amount_paise: Paise
    accepted_methods: dict[str, bool]
    tax_rate_percent: int = Field(default=0, ge=0, le=28)
    upgrade_pricing_mode: str = Field(default="price_difference", pattern="^(price_difference|full_price)$")
    upi_vpa: str = Field(default="examlms@icici", min_length=3, max_length=120)
    upi_merchant_name: str = Field(default="ExamLMS", min_length=2, max_length=120)


class PaymentSettingsOut(ResponseSchema):
    payments_enabled: bool
    min_amount_paise: int
    max_amount_paise: int
    accepted_methods: dict[str, bool]
    tax_rate_percent: int
    upgrade_pricing_mode: str
    upi_vpa: str
    upi_merchant_name: str
    gateway_provider: str = "razorpay"
    test_mode: bool = True
    updated_at: Timestamp


class PaymentSettingsResponse(SuccessResponse):
    settings: PaymentSettingsOut


# ---------------------------------------------------------------- student checkout & verification
class CheckoutPreviewRequest(RequestSchema):
    plan_id: id_field("plan_id", "1755000000001001")  # type: ignore[valid-type]
    course_id: CourseIdIn | None = None  # type: ignore[valid-type]
    action_type: str = Field(default="new", pattern="^(new|upgrade|renew)$")


class CheckoutSummaryOut(BaseModel):
    plan: SubscriptionPlanOut
    course_id: str | None
    course_title: str | None
    action_type: str
    original_amount_paise: int
    discount_paise: int
    discount_note: str | None
    taxable_paise: int
    tax_paise: int
    tax_rate_percent: int
    total_amount_paise: int
    currency: str = "INR"
    accepted_methods: dict[str, bool]
    payments_enabled: bool
    current_plan_name: str | None = None


class CheckoutPreviewResponse(SuccessResponse):
    summary: CheckoutSummaryOut


class StudentCheckoutRequest(RequestSchema):
    plan_id: id_field("plan_id", "1755000000001001")  # type: ignore[valid-type]
    course_id: CourseIdIn | None = None  # type: ignore[valid-type]
    payment_method: str = Field(default="upi", pattern="^(upi|gpay|phonepe|paytm|card|netbanking|wallet|razorpay|stripe)$")
    action_type: str = Field(default="new", pattern="^(new|upgrade|renew)$")
    student_name: str | None = Field(default=None, max_length=200)
    student_email: str | None = Field(default=None, max_length=200)


class GatewayCheckoutPayload(BaseModel):
    provider: str
    test_mode: bool
    key_id: str | None
    order_id: str
    amount: int
    currency: str
    seller_name: str
    upi_qr_payload: str | None
    expires_at: Timestamp | None


class StudentPaymentTransactionOut(ResponseSchema):
    tx_id: PublicIdOut = Field(validation_alias="public_id")
    transaction_ref: str
    user_id: PublicIdOut
    payer_user_id: PublicIdOut
    payer_role: str
    payment_scope: str
    student_count: int
    organization_id: PublicIdOut
    plan_id: str
    plan_code: str
    plan_name: str
    course_id: PublicIdOut | None
    course_title: str | None
    action_type: str
    original_amount_paise: int
    discount_paise: int
    tax_paise: int
    total_amount_paise: int
    currency: str
    payment_method: str
    gateway_provider: str
    gateway_order_id: str
    gateway_payment_id: str | None
    upi_qr_payload: str | None
    status: str
    failure_reason: str | None
    invoice_number: str | None
    expires_at: Timestamp | None
    paid_at: Timestamp | None
    created_at: Timestamp


class StudentCheckoutResponse(SuccessResponse):
    transaction: StudentPaymentTransactionOut
    checkout: GatewayCheckoutPayload


class VerifyStudentPaymentRequest(RequestSchema):
    razorpay_order_id: str = Field(min_length=3, max_length=100)
    razorpay_payment_id: str | None = Field(default=None, max_length=100)
    razorpay_signature: str | None = Field(default=None, max_length=200)
    outcome: str = Field(default="succeeded", pattern="^(succeeded|failed|pending)$")
    failure_reason: str | None = Field(default=None, max_length=300)


class TestGatewayCallbackRequest(RequestSchema):
    outcome: str = Field(default="captured", pattern="^(captured|failed)$")
    payment_id: str | None = Field(default=None, max_length=100)
    failure_reason: str | None = Field(default=None, max_length=300)


# ---------------------------------------------------------------- student subscription & history
class SubscriptionCourseOut(ResponseSchema):
    course_id: PublicIdOut
    course_title: str
    granted_at: Timestamp


class StudentSubscriptionOut(ResponseSchema):
    subscription_id: PublicIdOut = Field(validation_alias="public_id")
    plan_id: str
    plan_code: str
    plan_name: str
    price_paise: int
    duration_days: int
    max_courses: int | None
    features: list[str]
    assessment_access: dict[str, Any]
    certificate_level: str
    status: str
    starts_at: Timestamp | None
    ends_at: Timestamp | None
    created_at: Timestamp
    courses: list[SubscriptionCourseOut] = Field(default_factory=list)


class StudentSubscriptionOverviewResponse(SuccessResponse):
    active_subscription: StudentSubscriptionOut | None
    history: list[StudentSubscriptionOut]
    available_upgrades: list[SubscriptionPlanOut]
    latest_payment: StudentPaymentTransactionOut | None


class EnrollCourseUnderPlanRequest(RequestSchema):
    course_id: CourseIdIn  # type: ignore[valid-type]


class VerifyPaymentResponse(SuccessResponse):
    transaction: StudentPaymentTransactionOut
    subscription: StudentSubscriptionOut | None


class TransactionListResponse(SuccessResponse):
    transactions: list[StudentPaymentTransactionOut]
    page_context: PageContext


class ReceiptResponse(SuccessResponse):
    receipt: dict[str, Any]


class AdminPaymentReportsResponse(SuccessResponse):
    total_revenue_paise: int
    independent_revenue_paise: int
    institution_revenue_paise: int
    succeeded_count: int
    pending_count: int
    failed_count: int
    pending_requests_count: int
    active_subscriptions_count: int
    plan_breakdown: list[dict[str, Any]]
    institution_revenue: list[dict[str, Any]] = Field(default_factory=list)
    course_revenue: list[dict[str, Any]] = Field(default_factory=list)
    plan_revenue: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------- student account context & requests
class StudentAccountContextResponse(SuccessResponse):
    student_category: str  # "individual" | "institution"
    can_pay_directly: bool
    must_request_payment: bool
    organization_id: PublicIdOut | None


class CreatePaymentRequestIn(RequestSchema):
    course_id: CourseIdIn  # type: ignore[valid-type]
    plan_id: id_field("plan_id", "1755000000001001")  # type: ignore[valid-type]
    student_note: str | None = Field(default=None, max_length=500)


class DecisionNoteIn(RequestSchema):
    decision_note: str | None = Field(default=None, max_length=500)


class StudentPaymentRequestOut(ResponseSchema):
    request_id: PublicIdOut = Field(validation_alias="public_id")
    request_ref: str
    student_user_id: PublicIdOut
    student_name: str
    student_email: str
    organization_id: PublicIdOut
    course_id: PublicIdOut
    course_title: str
    plan_id: str
    plan_code: str
    plan_name: str
    amount_paise: int
    status: str
    student_note: str | None
    decision_note: str | None
    reviewed_by_user_id: PublicIdOut | None
    reviewed_at: Timestamp | None
    paid_by_user_id: PublicIdOut | None
    paid_at: Timestamp | None
    transaction_id: str | None
    created_at: Timestamp


class StudentPaymentRequestResponse(SuccessResponse):
    payment_request: StudentPaymentRequestOut


class StudentPaymentRequestListResponse(SuccessResponse):
    requests: list[StudentPaymentRequestOut]
    page_context: PageContext


# ---------------------------------------------------------------- institution head students & bulk checkout
class InstitutionStudentItem(BaseModel):
    student_user_id: str
    student_name: str
    student_email: str
    account_status: str
    selected_course_id: str | None = None
    selected_course_title: str | None = None
    active_plan_name: str | None = None
    active_subscription_ends_at: Timestamp | None = None
    payment_status: str  # "active_subscription" | "pending_request" | "approved_request" | "payment_initiated" | "failed" | "unpaid"
    pending_request_id: str | None = None
    pending_plan_id: str | None = None
    pending_plan_name: str | None = None


class InstitutionStudentListResponse(SuccessResponse):
    students: list[InstitutionStudentItem]
    approved_courses: list[dict[str, Any]]
    page_context: PageContext


class AssignStudentCourseIn(RequestSchema):
    student_user_id: id_field("student_user_id", "1755000000001001")  # type: ignore[valid-type]
    course_id: CourseIdIn  # type: ignore[valid-type]
    plan_id: id_field("plan_id", "1755000000001001") | None = None  # type: ignore[valid-type]


class InstitutionCheckoutPreviewIn(RequestSchema):
    student_ids: list[id_field("student_id", "1755000000001001")] = Field(min_length=1, max_length=200)  # type: ignore[valid-type]
    plan_id: id_field("plan_id", "1755000000001001")  # type: ignore[valid-type]
    course_id: CourseIdIn | None = None  # type: ignore[valid-type]
    request_ids: list[id_field("request_id", "1755000000001001")] = Field(default_factory=list)  # type: ignore[valid-type]


class InstitutionAllocationPreviewOut(BaseModel):
    student_user_id: str
    student_name: str
    student_email: str
    course_id: str | None
    course_title: str | None
    payment_request_id: str | None
    original_amount_paise: int
    discount_paise: int
    tax_paise: int
    total_amount_paise: int


class InstitutionCheckoutSummaryOut(BaseModel):
    plan: SubscriptionPlanOut
    student_count: int
    currency: str
    original_total_paise: int
    discount_total_paise: int
    tax_rate_percent: int
    tax_total_paise: int
    grand_total_paise: int
    allocations: list[InstitutionAllocationPreviewOut]
    accepted_methods: dict[str, bool]
    payments_enabled: bool


class InstitutionCheckoutPreviewResponse(SuccessResponse):
    summary: InstitutionCheckoutSummaryOut


class InstitutionCheckoutCreateIn(InstitutionCheckoutPreviewIn):
    payment_method: str = Field(default="upi", pattern="^(upi|gpay|phonepe|paytm|card|netbanking|wallet|razorpay|stripe)$")


class StudentPaymentAllocationOut(ResponseSchema):
    allocation_id: PublicIdOut = Field(validation_alias="public_id")
    transaction_id: str
    organization_id: PublicIdOut
    payer_user_id: PublicIdOut
    student_user_id: PublicIdOut
    student_name: str
    student_email: str
    course_id: PublicIdOut | None
    course_title: str | None
    plan_id: str
    plan_code: str
    plan_name: str
    original_amount_paise: int
    discount_paise: int
    tax_paise: int
    allocated_amount_paise: int
    status: str
    activated_at: Timestamp | None
    created_at: Timestamp


class InstitutionCheckoutSessionResponse(SuccessResponse):
    transaction: StudentPaymentTransactionOut
    allocations: list[StudentPaymentAllocationOut]
    gateway: GatewayCheckoutPayload


class InstitutionTransactionDetailResponse(SuccessResponse):
    transaction: StudentPaymentTransactionOut
    allocations: list[StudentPaymentAllocationOut]


class AllocationListResponse(SuccessResponse):
    allocations: list[StudentPaymentAllocationOut]
    page_context: PageContext
