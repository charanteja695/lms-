"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class Dashboard(StrEnum):
    """A dashboard key names a fixed shape (§5.9): which events feed it and how the response is laid out. A
    scheduled report references one, plus the filters it is run with."""

    INSTITUTION = "institution"  # an institution's own enrolment/completion/exam/placement funnel
    CONTENT = "content"  # platform-wide learning funnel (no per-course breakdown: see README)
    EXAM_INTEGRITY = "exam_integrity"
    SUPPORT = "support"
    HIRING = "hiring"  # platform-wide, or one employer's own jobs
    AI_USAGE = "ai_usage"
    BILLING = "billing"


class ReportFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ReportStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


class ReportFormat(StrEnum):
    CSV = "csv"
    JSON = "json"
