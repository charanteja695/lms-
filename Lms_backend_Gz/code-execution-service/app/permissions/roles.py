"""Role values this service checks. Mirror user-management's ``Role`` enum (same string values, same token
claim) — see ``lms-backend/user-management/app/permissions/roles.py``. This service never assigns or changes
roles, only reads them from the verified token.

Any signed-in user may run code and submit to published problems; only authoring, review and platform
configuration are restricted (see app/permissions/policy.py)."""

from enum import StrEnum


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"
