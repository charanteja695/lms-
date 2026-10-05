"""Who may do what.

  student                    browse and search jobs, see matches, apply, follow and withdraw, answer offers, set preferences
  recruiter                  their employer's jobs (draft, submit, pause, close) and those jobs' applications: screen, shortlist,
                             reject (a confirmed batch), move through the pipeline, extend offers, place
  employer admin             everything a recruiter does, plus the company profile (submit for verification)
  institution staff / head   their institution's students' applications and placements; a head also proposes placement drives
  careers.manage             verify employers, approve jobs, see everything
  super admin                everything
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


def is_employer_member(auth: AccessTokenClaims) -> bool:
    return auth.role in {Role.EMPLOYER_ADMIN, Role.RECRUITER} and auth.organization_id is not None


def is_employer_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.EMPLOYER_ADMIN and auth.organization_id is not None


def is_institution_staff(auth: AccessTokenClaims) -> bool:
    return auth.role in {Role.STAFF, Role.INSTITUTION_HEAD} and auth.organization_id is not None


def is_institution_head(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.INSTITUTION_HEAD and auth.organization_id is not None


def can_manage_careers(auth: AccessTokenClaims) -> bool:
    return is_super_admin(auth) or bool(auth.has_scope(Scope.CAREERS_MANAGE.value))


def owns_employer(auth: AccessTokenClaims, employer_org_id: int) -> bool:
    """A recruiter or admin of that employer (a careers manager may act for any)."""
    return (is_employer_member(auth) and auth.organization_id == employer_org_id) or can_manage_careers(auth)
