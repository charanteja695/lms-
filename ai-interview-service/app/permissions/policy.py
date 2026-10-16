"""Who may do what, as permissions from the access token (user-management's catalog; a super admin can grant or remove
any of them per person):

  interviews.practice  their own interviews: consent, take them, read their report (a screening report once it is released),
                       appeal, retake (by default a student)
  interviews.screen    their own company's screening plans and interviews: transcripts, evaluations, reviews, appeals
                       (by default an employer admin or recruiter)
  careers.manage       the platform's mock plans; read any interview; calibration and fairness audits
  super admin          every management action (taking an interview is a person's own, so it is never implied)
"""

from enum import StrEnum

from app.core.security import AccessTokenClaims
from app.permissions.roles import Role


class Scope(StrEnum):
    CAREERS_MANAGE = "careers.manage"  # values mirror user-management's AdminScope


PRACTICE = "interviews.practice"
SCREEN = "interviews.screen"


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def is_student(auth: AccessTokenClaims) -> bool:
    """Takes interviews as a candidate (held, not implied by being a super admin)."""
    return auth.has_scope(PRACTICE)


def is_employer_member(auth: AccessTokenClaims) -> bool:
    """Screens candidates for their own company."""
    return auth.organization_id is not None and auth.has_scope(SCREEN)


def can_manage_careers(auth: AccessTokenClaims) -> bool:
    return auth.can(Scope.CAREERS_MANAGE.value)


def owns_employer(auth: AccessTokenClaims, employer_org_id: int | None) -> bool:
    """A recruiter or admin of that employer (a careers manager may act for any)."""
    return (is_employer_member(auth) and employer_org_id is not None and auth.organization_id == employer_org_id) or can_manage_careers(auth)
