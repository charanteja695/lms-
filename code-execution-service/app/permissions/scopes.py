"""Admin scopes this service checks. Values mirror user-management's ``AdminScope`` (see
``lms-backend/user-management/app/permissions/roles.py``) since they travel in the same access token; this
service never grants or revokes them, only reads them from the token."""

from enum import StrEnum


class Scope(StrEnum):
    CONTENT_AUTHOR = "content.author"  # writes problems and test cases
    CONTENT_REVIEW = "content.review"  # reads everything, including hidden test cases and plagiarism flags
    EXAMS_MANAGE = "exams.manage"  # reads submissions and plagiarism flags of exams
