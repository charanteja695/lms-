"""Admin scopes this service checks (values mirror user-management's ``AdminScope``)."""

from enum import StrEnum


class Scope(StrEnum):
    CONTENT_AUTHOR = "content.author"  # course authors: evaluation sets, per-course FAQ, feedback summaries
    SUPPORT_MANAGE = "support.manage"  # platform support: every FAQ, escalations, conversation transcripts
    AI_MANAGE = "ai.manage"  # tutor index administration
