"""Who may do what.

  student            their own interviews: consent, take them, read their report (a screening report once it is released), appeal, retake
  recruiter/admin    their company's screening plans and interviews: read transcripts and evaluations, review the AI's recommendation, decide appeals
  careers.manage     the platform's mock plans; read any interview; calibration and fairness audits
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
    return auth.role == Role.STUDENT


def is_employer_member(auth: AccessTokenClaims) -> bool:
    return auth.role in {Role.EMPLOYER_ADMIN, Role.RECRUITER} and auth.organization_id is not None


def can_manage_careers(auth: AccessTokenClaims) -> bool:
    return is_super_admin(auth) or bool(auth.has_scope(Scope.CAREERS_MANAGE.value))


def owns_employer(auth: AccessTokenClaims, employer_org_id: int | None) -> bool:
    """A recruiter or admin of that employer (a careers manager may act for any)."""
    return (is_employer_member(auth) and employer_org_id is not None and auth.organization_id == employer_org_id) or can_manage_careers(auth)
