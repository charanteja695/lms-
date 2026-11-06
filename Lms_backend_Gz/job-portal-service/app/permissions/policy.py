"""Who may do what, as permissions from the access token (user-management's catalog; a super admin can grant or
remove any of them per person). The defaults are what each role gets:

  jobs.apply (student)                    browse and search jobs, see matches, apply, follow and withdraw, answer offers, set preferences
  jobs.hire (recruiter)      their employer's jobs (draft, submit, pause, close) and those jobs' applications: screen, shortlist,
                             reject (a confirmed batch), move through the pipeline, extend offers, place
  jobs.company.manage        (employer admin) the company profile, accepting or ending placement drives
  jobs.placements            (staff, head) their institution's students' applications and placements
  jobs.drives.propose        (head) proposing placement drives
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


def _member_may(auth: AccessTokenClaims, kind: str, permission: str, cell: str | None = None) -> bool:
    """``cell``: the permission-matrix cell that decides for heads, staff and students (company roles hold the key)."""
    held = auth.can_act(cell, permission) if cell else auth.has_scope(permission)
    return auth.organization_id is not None and auth.organization_type == kind and held


def is_student(auth: AccessTokenClaims, action: str = "view") -> bool:
    """Jobs, one action at a time (the Jobs page's cells): ``view`` browse and search, ``create`` apply and answer
    offers, ``revoke`` withdraw. A person's own; never implied by being a super admin."""
    return auth.role != Role.SUPER_ADMIN and auth.can_act(f"jobs.{action}", "jobs.apply")


def is_employer_member(auth: AccessTokenClaims) -> bool:
    """Hires for their own company."""
    return _member_may(auth, "employer", "jobs.hire")


def is_employer_admin(auth: AccessTokenClaims) -> bool:
    """Runs their own company's profile and its placement drives."""
    return _member_may(auth, "employer", "jobs.company.manage")


def is_institution_staff(auth: AccessTokenClaims) -> bool:
    """Follows their own institution's students' applications and placements."""
    return _member_may(auth, "institution", "jobs.placements", "placements.view")


def is_institution_head(auth: AccessTokenClaims) -> bool:
    """Proposes placement drives for their own institution."""
    return _member_may(auth, "institution", "jobs.drives.propose", "placements.create")


def can_manage_careers(auth: AccessTokenClaims) -> bool:
    return auth.can(Scope.CAREERS_MANAGE.value) or auth.role in (Role.SUPER_ADMIN, Role.ADMIN)


def owns_employer(auth: AccessTokenClaims, employer_org_id: int) -> bool:
    """A recruiter or admin of that employer (a careers manager may act for any)."""
    return (is_employer_member(auth) and auth.organization_id == employer_org_id) or can_manage_careers(auth)
