"""Who may do what, as permissions from the access token (user-management's catalog; a super admin can grant or
remove any of them per person). One place, so the rules read the same everywhere they are applied.

  certificates.own        their own certificates (by default a student; never implied by being a super admin)
  certificates.students   their own institution's students' certificates (staff, head)
  content.author / content.review   certificate templates; exams.manage   every certificate, revoke, regenerate
"""

from app.core.security import AccessTokenClaims
from app.permissions.roles import Role
from app.permissions.scopes import Scope


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def is_student(auth: AccessTokenClaims) -> bool:
    """Holds certificates of their own."""
    return auth.has_scope("certificates.own")


def is_institution_staff(auth: AccessTokenClaims) -> bool:
    """Sees their own institution's students' certificates."""
    return auth.organization_id is not None and auth.has_scope("certificates.students")


def can_author_templates(auth: AccessTokenClaims) -> bool:
    return auth.can(Scope.CONTENT_AUTHOR.value)


def can_publish_templates(auth: AccessTokenClaims) -> bool:
    return auth.can(Scope.CONTENT_REVIEW.value)


def can_manage_certificates(auth: AccessTokenClaims) -> bool:
    """See every certificate, revoke one, regenerate a PDF."""
    return auth.can(Scope.EXAMS_MANAGE.value)


def can_view_certificate(auth: AccessTokenClaims, *, student_user_id: int, organization_id: int | None) -> bool:
    """The student, the platform's exam managers, or the staff/head of the student's own institution."""
    if auth.user_id == student_user_id or can_manage_certificates(auth):
        return True
    return is_institution_staff(auth) and auth.organization_id == organization_id
