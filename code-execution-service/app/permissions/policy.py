"""Who may do what. One place, so the rules read the same everywhere they are applied."""

from app.core.security import AccessTokenClaims
from app.permissions.roles import Role
from app.permissions.scopes import Scope


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def can_author(auth: AccessTokenClaims) -> bool:
    """Create and edit problems, test cases and their lifecycle."""
    return is_super_admin(auth) or auth.has_scope(Scope.CONTENT_AUTHOR.value)


def can_review(auth: AccessTokenClaims) -> bool:
    """See hidden test cases, every submission and the plagiarism signal (read-only)."""
    return (
        can_author(auth)
        or auth.has_scope(Scope.CONTENT_REVIEW.value)
        or auth.has_scope(Scope.EXAMS_MANAGE.value)
    )
