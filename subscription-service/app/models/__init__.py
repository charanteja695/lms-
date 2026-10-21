"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.course_access import CourseAccess, CourseAccessPurchase
from app.models.course_ref import CourseRef
from app.models.course_request import CourseRequest
from app.models.institution_ref import InstitutionRef
from app.models.outbox_event import OutboxEvent
from app.models.seat_reservation import SeatReservation
from app.models.subscription import Subscription

__all__ = [
    "Base",
    "CourseAccess",
    "CourseAccessPurchase",
    "CourseRef",
    "CourseRequest",
    "InstitutionRef",
    "OutboxEvent",
    "SeatReservation",
    "Subscription",
]
