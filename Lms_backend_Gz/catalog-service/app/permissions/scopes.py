"""Platform admin scopes this service checks. Values mirror user-management's ``AdminScope``
(see ``lms-backend/user-management/app/permissions/roles.py``) since they travel in the same
access token; this service never grants or revokes them, only reads them from the token.
"""

from enum import StrEnum


class Scope(StrEnum):
    CONTENT_AUTHOR = "content.author"  # create course drafts, upload clips, write questions
    CONTENT_REVIEW = "content.review"  # review and publish course versions
