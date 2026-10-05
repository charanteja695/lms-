"""Who may do what. One place, so the rules read the same everywhere they are applied.

Live monitoring and integrity review belong to the platform's exam managers (``exams.manage``), to the staff and head of
the *student's own institution* for platform tests, and to the owning employer's members for that employer's hiring
assessments (a test with an owning organisation). An institution's staff never see an employer's hiring assessment.
"""

from enum import StrEnum

from app.core.security import AccessTokenClaims


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    INSTITUTION_HEAD = "institution_head"
    STAFF = "staff"
    STUDENT = "student"
    EMPLOYER_ADMIN = "employer_admin"
    RECRUITER = "recruiter"


EXAMS_MANAGE = "exams.manage"


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def is_student(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.STUDENT


def can_manage_exams(auth: AccessTokenClaims) -> bool:
    return is_super_admin(auth) or auth.has_scope(EXAMS_MANAGE)


def is_institution_staff(auth: AccessTokenClaims) -> bool:
    return auth.role in {Role.STAFF, Role.INSTITUTION_HEAD} and auth.organization_id is not None


def is_employer_member(auth: AccessTokenClaims) -> bool:
    return auth.role in {Role.EMPLOYER_ADMIN, Role.RECRUITER} and auth.organization_id is not None


def can_monitor(auth: AccessTokenClaims, *, student_organization_id: int | None, test_owner_id: int | None) -> bool:
    """See a live session, warn/pause/resume/terminate it, and review its case."""
    if can_manage_exams(auth):
        return True
    if test_owner_id is not None:
        return is_employer_member(auth) and auth.organization_id == test_owner_id
    return is_institution_staff(auth) and auth.organization_id == student_organization_id


def can_decide_appeals(auth: AccessTokenClaims) -> bool:
    """An appeal goes above the first reviewer: the platform's exam managers only."""
    return can_manage_exams(auth)
