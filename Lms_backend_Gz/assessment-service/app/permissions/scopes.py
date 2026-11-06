"""Admin scopes this service checks. Values mirror user-management's ``AdminScope`` (see
``lms-backend/user-management/app/permissions/roles.py``) since they travel in the same access token; this
service never grants or revokes them, only reads them from the token."""

from enum import StrEnum


class Scope(StrEnum):
    CONTENT_AUTHOR = "content.author"  # writes questions and tests
    CONTENT_REVIEW = "content.review"  # approves questions and tests, reads answer keys
    EXAMS_MANAGE = "exams.manage"  # schedules exams, grades, manages live attempts and results
