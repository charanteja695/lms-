"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.attempt import Attempt, AttemptAnswer, AttemptEvent, AttemptQuestion, AttemptSection, CodingSubmission
from app.models.idempotency_key import IdempotencyKey
from app.models.outbox_event import OutboxEvent
from app.models.processed_event import ProcessedEvent
from app.models.question import Question, QuestionStats, QuestionVersion, QuestionVersionTag
from app.models.refs import EnrollmentRef, VersionRef, VersionTarget
from app.models.test import SectionSlot, Test, TestAssignment, TestSchedule, TestSection

__all__ = [
    "Attempt",
    "AttemptAnswer",
    "AttemptEvent",
    "AttemptQuestion",
    "AttemptSection",
    "Base",
    "CodingSubmission",
    "EnrollmentRef",
    "IdempotencyKey",
    "OutboxEvent",
    "ProcessedEvent",
    "Question",
    "QuestionStats",
    "QuestionVersion",
    "QuestionVersionTag",
    "SectionSlot",
    "Test",
    "TestAssignment",
    "TestSchedule",
    "TestSection",
    "VersionRef",
    "VersionTarget",
]
