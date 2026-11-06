"""Who may do what, as permissions from the access token (user-management's catalog; a super admin can grant or
remove any of them per person). One place, so the rules read the same everywhere they are applied.

  code.practice      run code and submit solutions (by default students, staff and heads)
  code.submissions   keep and read their own submissions list (by default a student)
  content.author     problems and test cases; content.review / exams.manage   hidden cases, every submission
"""

from app.core.security import AccessTokenClaims
from app.permissions.roles import Role
from app.permissions.scopes import Scope


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def can_author(auth: AccessTokenClaims) -> bool:
    """Create and edit problems, test cases and their lifecycle."""
    return auth.can(Scope.CONTENT_AUTHOR.value)


def can_review(auth: AccessTokenClaims) -> bool:
    """See hidden test cases, every submission and the plagiarism signal (read-only)."""
    return (
        can_author(auth)
        or auth.has_scope(Scope.CONTENT_REVIEW.value)
        or auth.has_scope(Scope.EXAMS_MANAGE.value)
    )


def can_practice(auth: AccessTokenClaims) -> bool:
    """Run code and submit solutions."""
    return auth.has_scope("code.practice") or can_review(auth)


def can_list_own_submissions(auth: AccessTokenClaims) -> bool:
    """The "My submissions" history (a reviewer sees every submission anyway)."""
    return auth.has_scope("code.submissions") or can_review(auth)
