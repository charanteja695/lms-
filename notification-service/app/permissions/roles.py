"""Role values this service checks. Mirror user-management's ``Role`` enum (same string values,
same token claim) — see ``lms-backend/user-management/app/permissions/roles.py``. This service
never assigns or changes roles, only reads them from the verified token.

Every signed-in user has their own inbox and preferences, so no role is needed for those. Only
platform-wide operations (message templates, delivery monitoring) are restricted."""

from enum import StrEnum


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"  # edits templates and monitors deliveries
