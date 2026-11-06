"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.course_ref import CourseRef
from app.models.delivery import Delivery
from app.models.notification import Notification
from app.models.notification_preference import NotificationPreference
from app.models.outbox_event import OutboxEvent
from app.models.processed_event import ProcessedEvent
from app.models.template_override import TemplateOverride
from app.models.user_ref import UserRef

__all__ = [
    "Base",
    "CourseRef",
    "Delivery",
    "Notification",
    "NotificationPreference",
    "OutboxEvent",
    "ProcessedEvent",
    "TemplateOverride",
    "UserRef",
]
