"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class ConversationMode(StrEnum):
    LEARNING = "learning"  # course content RAG + the student's current context (docs/PRODUCT.md §5.5)
    SUPPORT = "support"  # FAQ + read-only lookups about the student's own enrolment / attempts / certificates


class ConversationStatus(StrEnum):
    OPEN = "open"
    ESCALATED = "escalated"  # a person has been asked; the tutor keeps answering but the ticket is the record
    CLOSED = "closed"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageKind(StrEnum):
    ANSWER = "answer"  # a grounded model answer
    FAQ = "faq"  # a published FAQ answer returned without calling a model
    LOW_CONFIDENCE = "low_confidence"  # nothing relevant was found; no model answer attempted
    ESCALATION = "escalation"  # the student was handed to a person
    BLOCKED = "blocked"  # moderation stopped the call
    QUESTION = "question"  # the student's own message


class EscalationReason(StrEnum):
    LOW_CONFIDENCE = "low_confidence"
    USER_REQUESTED = "user_requested"
    SENSITIVE_TOPIC = "sensitive_topic"  # money, integrity or access (docs/PRODUCT.md §5.5)


class EscalationCategory(StrEnum):
    LEARNING = "learning"  # routed to the batch's staff
    TECHNICAL = "technical"  # routed to platform support
    BILLING = "billing"
    INTEGRITY = "integrity"
    ACCESS = "access"


class EscalationStatus(StrEnum):
    PENDING = "pending"  # not yet delivered to support-service
    CREATED = "created"  # a ticket exists
    FAILED = "failed"  # gave up; a support manager can retry


class FaqScope(StrEnum):
    PLATFORM = "platform"
    ORGANIZATION = "organization"
    COURSE = "course"


class FaqStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class Rating(StrEnum):
    UP = "up"
    DOWN = "down"


class AttemptState(StrEnum):
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    FINALIZED = "finalized"


class RetrievalMethod(StrEnum):
    DENSE = "dense"
    LEXICAL = "lexical"  # the embedding call was unavailable, so word overlap was used instead
    NONE = "none"
