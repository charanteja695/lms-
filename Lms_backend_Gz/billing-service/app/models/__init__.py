"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.billing import (
    BillingProfile,
    CoursePurchase,
    CreditNote,
    GatewayEvent,
    Invoice,
    InvoiceLine,
    NumberCounter,
    OrgPlan,
    Payment,
    PriceItem,
    Quote,
)
from app.models.outbox_event import OutboxEvent
from app.models.processed_event import ProcessedEvent
from app.models.refs import OrgRef
from app.models.institutional_request import InstitutionalPurchaseRequest
from app.models.institutional_pricing import CourseInstitutionalPricing, CoursePricingChangeAudit
from app.models.student_subscription import (
    PaymentSettings,
    StudentPaymentAllocation,
    StudentPaymentRequest,
    StudentPaymentTransaction,
    StudentSubscription,
    StudentSubscriptionCourse,
    SubscriptionPlan,
)

__all__ = [
    "Base",
    "BillingProfile",
    "CourseInstitutionalPricing",
    "CoursePurchase",
    "CreditNote",
    "GatewayEvent",
    "InstitutionalPurchaseRequest",
    "Invoice",
    "InvoiceLine",
    "NumberCounter",
    "OrgPlan",
    "OrgRef",
    "OutboxEvent",
    "Payment",
    "PaymentSettings",
    "PriceItem",
    "ProcessedEvent",
    "Quote",
    "StudentPaymentAllocation",
    "StudentPaymentRequest",
    "StudentPaymentTransaction",
    "StudentSubscription",
    "StudentSubscriptionCourse",
    "SubscriptionPlan",
]
