"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class CourseRequestStatus(StrEnum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class SubscriptionStatus(StrEnum):
    """approved course request -> active subscription -> expired (term ended) or cancelled early."""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class CourseAccessStatus(StrEnum):
    """A learner's bought access: active until ``ends_at``, then expired (buying again re-opens it)."""

    ACTIVE = "active"
    EXPIRED = "expired"


class InstitutionStatus(StrEnum):
    """Local mirror of user-management's institution status (see app/models/institution_ref.py):
    only the values this service needs to react to."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class CourseAvailability(StrEnum):
    """Local mirror of catalog-service's course lifecycle: only whether it can be requested."""

    PUBLISHED = "published"
    RETIRED = "retired"
