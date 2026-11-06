"""Admin scopes this service checks (values mirror user-management's ``AdminScope``)."""

from enum import StrEnum


class Scope(StrEnum):
    CONTENT_AUTHOR = "content.author"  # writes certificate templates
    CONTENT_REVIEW = "content.review"  # activates and archives templates
    EXAMS_MANAGE = "exams.manage"  # sees every certificate, revokes, regenerates
