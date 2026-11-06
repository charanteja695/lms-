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

__all__ = [
    "Base", "BillingProfile", "CoursePurchase", "CreditNote", "GatewayEvent", "Invoice", "InvoiceLine", "NumberCounter", "OrgPlan", "OrgRef", "OutboxEvent", "Payment", "PriceItem", "ProcessedEvent", "Quote",
]
