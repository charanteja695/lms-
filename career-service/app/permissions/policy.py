"""Who may see or change what, as permissions from the access token (user-management's catalog; a super admin can
grant or remove any of them per person).

  career.profile     their own profile, resumes, shares (by default a student; never implied by being a super admin)
  career.students    read a student's profile inside their own institution (placement work); never edit it (staff, head)
  careers.manage     read any student's profile; templates
  super admin        everything
"""

from enum import StrEnum

from app.core.security import AccessTokenClaims
from app.permissions.roles import Role


class Scope(StrEnum):
    CAREERS_MANAGE = "careers.manage"  # values mirror user-management's AdminScope


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def is_student(auth: AccessTokenClaims) -> bool:
    """Keeps their own career profile and resumes."""
    return auth.has_scope("career.profile")


def is_institution_staff(auth: AccessTokenClaims) -> bool:
    """Reads their own institution's students' profiles."""
    return auth.organization_id is not None and auth.has_scope("career.students")


def can_manage_careers(auth: AccessTokenClaims) -> bool:
    return auth.can(Scope.CAREERS_MANAGE.value)


def can_view_student_profile(auth: AccessTokenClaims, *, student_user_id: int, student_organization_id: int | None) -> bool:
    if auth.user_id == student_user_id or can_manage_careers(auth):
        return True
    return is_institution_staff(auth) and student_organization_id is not None and auth.organization_id == student_organization_id
