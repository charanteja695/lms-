"""Who may do what. One place, so the rules read the same everywhere they are applied."""

from app.core.security import AccessTokenClaims
from app.permissions.roles import Role
from app.permissions.scopes import Scope


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def is_student(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.STUDENT


def is_institution_staff(auth: AccessTokenClaims) -> bool:
    return auth.role in {Role.STAFF, Role.INSTITUTION_HEAD} and auth.organization_id is not None


def can_author_templates(auth: AccessTokenClaims) -> bool:
    return is_super_admin(auth) or auth.has_scope(Scope.CONTENT_AUTHOR.value)


def can_publish_templates(auth: AccessTokenClaims) -> bool:
    return is_super_admin(auth) or auth.has_scope(Scope.CONTENT_REVIEW.value)


def can_manage_certificates(auth: AccessTokenClaims) -> bool:
    """See every certificate, revoke one, regenerate a PDF."""
    return is_super_admin(auth) or auth.has_scope(Scope.EXAMS_MANAGE.value)


def can_view_certificate(auth: AccessTokenClaims, *, student_user_id: int, organization_id: int | None) -> bool:
    """The student, the platform's exam managers, or the staff/head of the student's own institution."""
    if auth.user_id == student_user_id or can_manage_certificates(auth):
        return True
    return is_institution_staff(auth) and auth.organization_id == organization_id
