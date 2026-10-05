"""Roles and statuses.

Values are stored as plain strings (not native DB enums) so new roles or statuses can
be introduced later without a type migration.
"""

from enum import StrEnum


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    INSTITUTION_HEAD = "institution_head"
    STAFF = "staff"
    STUDENT = "student"
    EMPLOYER_ADMIN = "employer_admin"  # manages a hiring company's recruiters
    RECRUITER = "recruiter"


class OrganizationType(StrEnum):
    INSTITUTION = "institution"  # colleges, schools, training centres
    EMPLOYER = "employer"  # hiring companies


class AdminScope(StrEnum):
    """Platform responsibilities of an admin. Other services check them from the access token."""

    ACCOUNTS_MANAGE = "accounts.manage"  # own institutions and their members
    CAREERS_MANAGE = "careers.manage"  # own employers and their recruiters
    CONTENT_AUTHOR = "content.author"
    CONTENT_REVIEW = "content.review"
    EXAMS_MANAGE = "exams.manage"
    SUPPORT_MANAGE = "support.manage"
    AI_MANAGE = "ai.manage"
    ANALYTICS_VIEW = "analytics.view"  # platform-wide dashboards (analytics-service)
    BILLING_MANAGE = "billing.manage"  # quotes, invoices, payments, credit notes (billing-service)


DEFAULT_ADMIN_SCOPES: tuple[AdminScope, ...] = (AdminScope.ACCOUNTS_MANAGE,)
# The scope an admin needs to own organisations of each type.
SCOPE_FOR_ORGANIZATION: dict[OrganizationType, AdminScope] = {
    OrganizationType.INSTITUTION: AdminScope.ACCOUNTS_MANAGE,
    OrganizationType.EMPLOYER: AdminScope.CAREERS_MANAGE,
}


# Higher number = higher in the hierarchy.
ROLE_LEVELS: dict[Role, int] = {
    Role.SUPER_ADMIN: 100,
    Role.ADMIN: 80,
    Role.INSTITUTION_HEAD: 60,
    Role.STAFF: 40,
    Role.STUDENT: 20,
    Role.EMPLOYER_ADMIN: 60,
    Role.RECRUITER: 40,
}

INSTITUTION_MEMBER_ROLES: frozenset[Role] = frozenset({Role.INSTITUTION_HEAD, Role.STAFF, Role.STUDENT})
EMPLOYER_MEMBER_ROLES: frozenset[Role] = frozenset({Role.EMPLOYER_ADMIN, Role.RECRUITER})
# Roles that must belong to exactly one organisation (institution or employer).
ORGANIZATION_SCOPED_ROLES: frozenset[Role] = INSTITUTION_MEMBER_ROLES | EMPLOYER_MEMBER_ROLES


def organization_type_for(role: str) -> OrganizationType | None:
    if role in INSTITUTION_MEMBER_ROLES:
        return OrganizationType.INSTITUTION
    if role in EMPLOYER_MEMBER_ROLES:
        return OrganizationType.EMPLOYER
    return None


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"  # exists, cannot log in
    DELETED = "deleted"  # soft-deleted, hidden from normal queries


class InstitutionStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class StatusChange(StrEnum):
    """Statuses that may be set through a PATCH .../status call (delete has its own endpoint)."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


def parse_role(value: str) -> Role | None:
    try:
        return Role(value)
    except ValueError:
        return None
