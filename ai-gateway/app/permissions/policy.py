"""Who may do what. One place, so the rules read the same everywhere they are applied.

The completion/embedding/speech API has no per-person policy at all: it is called by other services with the
internal service token (see app/api/deps.py::require_internal_caller), on behalf of whichever org and user those
services already authenticated. Everything below governs only the admin API (prompts, quotas, logs, model routing).
"""

from app.core.security import AccessTokenClaims
from app.permissions.roles import Role
from app.permissions.scopes import Scope


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def is_institution_staff(auth: AccessTokenClaims) -> bool:
    return auth.role in {Role.STAFF, Role.INSTITUTION_HEAD} and auth.organization_id is not None


def can_manage_ai(auth: AccessTokenClaims) -> bool:
    """Manage the prompt registry and model routing, and see any org's usage and logs."""
    return is_super_admin(auth) or auth.has_scope(Scope.AI_MANAGE.value)


def can_view_org_usage(auth: AccessTokenClaims, *, organization_id: int) -> bool:
    """A platform AI manager, or that org's own staff/head looking at their own institution's spend."""
    if can_manage_ai(auth):
        return True
    return is_institution_staff(auth) and auth.organization_id == organization_id
