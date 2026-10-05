"""Who may see or change what.

  student                    their own profile, resumes, shares (and nobody else's)
  institution staff / head  read a student's profile inside their own institution (placement work); never edit it
  careers.manage            read any student's profile; templates
  super admin               everything
"""

from enum import StrEnum

from app.core.security import AccessTokenClaims
from app.permissions.roles import Role


class Scope(StrEnum):
    CAREERS_MANAGE = "careers.manage"  # values mirror user-management's AdminScope


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def is_student(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.STUDENT


def is_institution_staff(auth: AccessTokenClaims) -> bool:
    return auth.role in {Role.STAFF, Role.INSTITUTION_HEAD} and auth.organization_id is not None


def can_manage_careers(auth: AccessTokenClaims) -> bool:
    return is_super_admin(auth) or bool(auth.has_scope(Scope.CAREERS_MANAGE.value))


def can_view_student_profile(auth: AccessTokenClaims, *, student_user_id: int, student_organization_id: int | None) -> bool:
    if auth.user_id == student_user_id or can_manage_careers(auth):
        return True
    return is_institution_staff(auth) and student_organization_id is not None and auth.organization_id == student_organization_id
