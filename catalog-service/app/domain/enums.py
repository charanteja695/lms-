"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class ContentStatus(StrEnum):
    """Course version (and learning path) lifecycle; see docs/PRODUCT.md §3.2.

    draft --submit--> in_review --approve--> published (immutable) --retire--> archived
                          |
                          '--reject--> draft
    """

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ItemType(StrEnum):
    VIDEO = "video"
    PDF = "pdf"  # a document from media-service, read in the player
    NOTES = "notes"
    PRACTICE = "practice"
    QUIZ = "quiz"  # topic test; the question bank itself lives in assessment-service


class UnlockMode(StrEnum):
    SEQUENTIAL = "sequential"
    DRIP = "drip"  # schedule set by the batch (learning-service)


class ReviewAction(StrEnum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETIRED = "retired"
