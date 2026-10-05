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
    scopes: tuple[str, ...]
    token_version: int
    token_id: str
    issued_at: int
    expires_at: datetime

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes
