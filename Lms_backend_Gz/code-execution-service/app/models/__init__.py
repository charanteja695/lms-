"""Import every model here so Base.metadata (and Alembic) sees all tables."""

from app.db.base import Base
from app.models.code_fingerprint import CodeFingerprint
from app.models.idempotency_key import IdempotencyKey
from app.models.language import Language
from app.models.outbox_event import OutboxEvent
from app.models.problem import Problem
from app.models.run import Run
from app.models.saved_code import SavedCode
from app.models.submission import Submission
from app.models.submission_result import SubmissionResult
from app.models.test_case import TestCase

__all__ = [
    "Base",
    "CodeFingerprint",
    "IdempotencyKey",
    "Language",
    "OutboxEvent",
    "Problem",
    "Run",
    "SavedCode",
    "Submission",
    "SubmissionResult",
    "TestCase",
]
