"""Who may see what (docs/PRODUCT.md §5.9).

  institution head/staff    their own institution's dashboard only (`organization_id` from the token)
  employer admin/recruiter  their own company's hiring-funnel dashboard only
  platform admin            a platform-wide dashboard, gated by the scope that already manages that domain
                             elsewhere (`content.review`, `exams.manage`, `support.manage`, `careers.manage`,
                             `ai.manage`, `billing.manage`) — or the catch-all `analytics.view`
  super admin               everything
"""

from enum import StrEnum

from app.core.security import AccessTokenClaims
from app.permissions.roles import Role


class Scope(StrEnum):
    ANALYTICS_VIEW = "analytics.view"
    CONTENT_REVIEW = "content.review"
    EXAMS_MANAGE = "exams.manage"
    SUPPORT_MANAGE = "support.manage"
    CAREERS_MANAGE = "careers.manage"
    AI_MANAGE = "ai.manage"
    BILLING_MANAGE = "billing.manage"


OWN = "analytics.own"  # their own organisation's dashboards and reports


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def can_view_platform(auth: AccessTokenClaims, *domain_scopes: Scope) -> bool:
    """A platform admin sees a platform-wide dashboard if they hold the scope that manages that domain, or the
    catch-all `analytics.view`. A super admin always can."""
    return auth.can(Scope.ANALYTICS_VIEW.value) or any(auth.has_scope(s.value) for s in domain_scopes)


def _own(auth: AccessTokenClaims, kind: str) -> bool:
    return auth.organization_id is not None and auth.organization_type == kind and auth.has_scope(OWN)


def is_institution_member(auth: AccessTokenClaims) -> bool:
    """Sees their own institution's dashboards (``analytics.own``; by default its staff and head)."""
    return _own(auth, "institution")


def is_employer_member(auth: AccessTokenClaims) -> bool:
    """Sees their own company's hiring dashboard (``analytics.own``; by default its admin and recruiters)."""
    return _own(auth, "employer")
