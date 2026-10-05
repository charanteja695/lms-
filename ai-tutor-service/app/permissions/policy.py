"""Who may do what. One place, so the rules read the same everywhere they are applied."""

from app.core.security import AccessTokenClaims
from app.domain.enums import FaqScope
from app.permissions.roles import Role
from app.permissions.scopes import Scope


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def is_student(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.STUDENT


def is_institution_staff(auth: AccessTokenClaims) -> bool:
    return auth.role in {Role.STAFF, Role.INSTITUTION_HEAD} and auth.organization_id is not None


def can_manage_support(auth: AccessTokenClaims) -> bool:
    """Every FAQ, every escalation, any conversation's transcript."""
    return is_super_admin(auth) or bool(auth.has_scope(Scope.SUPPORT_MANAGE.value))


def can_author(auth: AccessTokenClaims) -> bool:
    """Course authors: a course's FAQ, its evaluation sets and its feedback."""
    return is_super_admin(auth) or bool(auth.has_scope(Scope.CONTENT_AUTHOR.value))


def can_manage_index(auth: AccessTokenClaims) -> bool:
    return is_super_admin(auth) or bool(auth.has_scope(Scope.AI_MANAGE.value))


def can_manage_faq(auth: AccessTokenClaims, scope: str, *, organization_id: int | None) -> bool:
    if can_manage_support(auth):
        return True
    if scope == FaqScope.COURSE:
        return can_author(auth)
    if scope == FaqScope.ORGANIZATION:
        return is_institution_staff(auth) and auth.organization_id == organization_id
    return False


def can_view_conversation(auth: AccessTokenClaims, *, organization_id: int | None) -> bool:
    """A support manager, or the staff/head of the student's own institution (to promote a good answer to the FAQ)."""
    return can_manage_support(auth) or (is_institution_staff(auth) and auth.organization_id == organization_id)
