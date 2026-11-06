"""Role values this service checks. Mirror user-management's ``Role`` enum (same string values, same token
claim) — see ``lms-backend/user-management/app/permissions/roles.py``. This service never assigns or changes
roles, only reads them from the verified token."""

from enum import StrEnum


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    INSTITUTION_HEAD = "institution_head"
    STAFF = "staff"
    STUDENT = "student"
    EMPLOYER_ADMIN = "employer_admin"
    RECRUITER = "recruiter"
