"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.content import ContentChunk, IndexJob
from app.models.conversation import Conversation, Escalation, Feedback, HintProgress, Message
from app.models.evaluation import EvalCase, EvalRun, EvalSet
from app.models.faq import FaqEntry
from app.models.outbox_event import OutboxEvent
from app.models.processed_event import ProcessedEvent
from app.models.refs import AttemptRef, CertificateRef, CourseVersionRef, EnrollmentRef, ItemRef

__all__ = [
    "AttemptRef",
    "Base",
    "CertificateRef",
    "ContentChunk",
    "Conversation",
    "CourseVersionRef",
    "EnrollmentRef",
    "Escalation",
    "EvalCase",
    "EvalRun",
    "EvalSet",
    "FaqEntry",
    "Feedback",
    "HintProgress",
    "IndexJob",
    "ItemRef",
    "Message",
    "OutboxEvent",
    "ProcessedEvent",
]
