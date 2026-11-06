"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class InstitutionStatus(StrEnum):
    """Local mirror of user-management's institution status — only the values this service
    needs to react to (see app/models/institution_ref.py)."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class CourseVersionStatus(StrEnum):
    """Local mirror of catalog-service's course version lifecycle: only whether new batches
    may still be created against it (see app/models/course_version_ref.py)."""

    PUBLISHED = "published"
    RETIRED = "retired"


class BatchStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    WITHDRAWN = "withdrawn"


class UnlockMode(StrEnum):
    """Local mirror of catalog-service's course_rules.unlock_mode."""

    SEQUENTIAL = "sequential"
    DRIP = "drip"
