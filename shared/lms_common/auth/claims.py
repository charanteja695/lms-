"""Access token claims, decoded and validated (never issued) by every non-issuing service."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """All identifiers are public ids (see ``lms_common.ids``), not internal database keys."""

    user_id: int
    session_id: int
    role: str
    organization_id: int | None
    organization_type: str | None
    # The person's effective permissions (feature keys): role defaults + admin scopes + per-person grants -
    # per-person removals, computed by user-management at sign-in. Admin scopes are permission keys too.
    scopes: tuple[str, ...]
    token_version: int
    token_id: str
    issued_at: int
    expires_at: datetime
    # An admin's institutions (the ones they look after). Platform-wide permissions such as accounts.manage reach
    # only these for an admin; the super admin reaches every organisation. Empty for everyone else.
    admin_organization_ids: tuple[int, ...] = ()

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

    def organizations_in_care(self) -> tuple[int, ...] | None:
        """Whose records a platform-wide permission reaches: ``None`` = every organisation (the super admin), else the
        admin's own institutions (empty for anyone who is not an admin)."""
        return None if self.role == "super_admin" else self.admin_organization_ids

    def can(self, permission: str) -> bool:
        """Whether this person holds ``permission``. A super admin holds every permission and can't be restricted."""
        return self.role == "super_admin" or permission in self.scopes
