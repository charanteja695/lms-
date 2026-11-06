"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.assessment_result import AssessmentResult
from app.models.batch import Batch
from app.models.course_version_ref import CourseVersionRef
from app.models.enrollment import Enrollment
from app.models.institution_ref import InstitutionRef
from app.models.item_progress import ItemProgress
from app.models.module_ref import ModuleRef
from app.models.outbox_event import OutboxEvent
from app.models.topic_item_ref import TopicItemRef
from app.models.topic_ref import TopicRef

__all__ = [
    "AssessmentResult",
    "Base",
    "Batch",
    "CourseVersionRef",
    "Enrollment",
    "InstitutionRef",
    "ItemProgress",
    "ModuleRef",
    "OutboxEvent",
    "TopicItemRef",
    "TopicRef",
]
