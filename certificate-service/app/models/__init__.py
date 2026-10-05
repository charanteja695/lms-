"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.certificate import Certificate, CertificateEvent
from app.models.outbox_event import OutboxEvent
from app.models.processed_event import ProcessedEvent
from app.models.refs import CourseRef, InstitutionRef, UserRef
from app.models.template import CertificateTemplate

__all__ = [
    "Base",
    "Certificate",
    "CertificateEvent",
    "CertificateTemplate",
    "CourseRef",
    "InstitutionRef",
    "OutboxEvent",
    "ProcessedEvent",
    "UserRef",
]
