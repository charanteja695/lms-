"""Role values this service checks. Mirror user-management's ``Role`` enum (same string values,
same token claim) — see ``lms-backend/user-management/app/permissions/roles.py``. This service
never assigns or changes roles, only reads them from the verified token."""

from enum import StrEnum


class Role(StrEnum):
    INSTITUTION_HEAD = "institution_head"  # submits course requests for their own institution
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
