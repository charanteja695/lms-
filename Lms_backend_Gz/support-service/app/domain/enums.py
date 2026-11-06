"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class TicketStatus(StrEnum):
    """docs/PRODUCT.md §5.5: open → assigned → waiting_on_student → resolved → closed."""

    OPEN = "open"
    ASSIGNED = "assigned"
    WAITING_ON_STUDENT = "waiting_on_student"
    RESOLVED = "resolved"
    CLOSED = "closed"


ACTIVE_STATUSES = (TicketStatus.OPEN, TicketStatus.ASSIGNED, TicketStatus.WAITING_ON_STUDENT)


class Category(StrEnum):
    LEARNING = "learning"  # a doubt about course content
    TECHNICAL = "technical"  # the platform does not work
    BILLING = "billing"
    INTEGRITY = "integrity"  # a test's integrity decision
    ACCESS = "access"  # login, enrolment, seats
    OTHER = "other"


class Queue(StrEnum):
    BATCH_STAFF = "batch_staff"  # the student's own institution's staff
    PLATFORM_SUPPORT = "platform_support"
    EXAM_TEAM = "exam_team"


# Where a category is handled (docs/PRODUCT.md §5.5: "routed to the batch staff for learning doubts or to platform
# support for technical issues"); money and access go to platform support, integrity to the exam team.
QUEUE_FOR_CATEGORY: dict[Category, Queue] = {
    Category.LEARNING: Queue.BATCH_STAFF,
    Category.TECHNICAL: Queue.PLATFORM_SUPPORT,
    Category.BILLING: Queue.PLATFORM_SUPPORT,
    Category.ACCESS: Queue.PLATFORM_SUPPORT,
    Category.OTHER: Queue.PLATFORM_SUPPORT,
    Category.INTEGRITY: Queue.EXAM_TEAM,
}


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class Source(StrEnum):
    PORTAL = "portal"  # the student opened it
    AI_TUTOR = "ai-tutor"  # the tutor handed a conversation over


class MessageKind(StrEnum):
    PUBLIC = "public"  # visible to the student
    INTERNAL = "internal"  # agents only
    SYSTEM = "system"  # what the service did (visible to the student)


class AuthorRole(StrEnum):
    REQUESTER = "requester"
    AGENT = "agent"
    SYSTEM = "system"


class CannedScope(StrEnum):
    PLATFORM = "platform"
    ORGANIZATION = "organization"
