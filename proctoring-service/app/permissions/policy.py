"""Who may do what. One place, so the rules read the same everywhere they are applied.

Live monitoring and integrity review belong to the platform's exam managers (``exams.manage``), to the staff and head of
the *student's own institution* for platform tests, and to the owning employer's members for that employer's hiring
assessments (a test with an owning organisation). An institution's staff never see an employer's hiring assessment.

Permissions come from the access token (user-management's catalog; a super admin can grant or remove any per person):
  proctoring.take      sit proctored exams; their own integrity cases and appeals (by default a student)
  proctoring.monitor   their own organisation's live sessions and cases (staff, head, employer admin, recruiter)
  exams.manage         every session and case; appeals
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


TAKE, MONITOR = "proctoring.take", "proctoring.monitor"


def is_student(auth: AccessTokenClaims) -> bool:
    """Sits proctored exams (a person's own; never implied by being a super admin)."""
    return auth.has_scope(TAKE)


def can_manage_exams(auth: AccessTokenClaims) -> bool:
    return auth.can(EXAMS_MANAGE)


def _monitors(auth: AccessTokenClaims, kind: str, action: str = "view") -> bool:
    """``action``: ``view`` (watch sessions, read cases) or ``update`` (warn/pause/stop a session, decide a case) — the
    Live proctoring page's cells for institution staff; company roles hold the coarse key."""
    return auth.organization_id is not None and auth.organization_type == kind and auth.can_act(f"proctoring.{action}", MONITOR)


def is_institution_staff(auth: AccessTokenClaims, action: str = "view") -> bool:
    """Watches (or acts on) their own institution's students' sessions on platform tests."""
    return _monitors(auth, "institution", action)


def is_employer_member(auth: AccessTokenClaims) -> bool:
    """Watches their own company's hiring-assessment sessions."""
    return _monitors(auth, "employer")


def can_monitor(auth: AccessTokenClaims, *, student_organization_id: int | None, test_owner_id: int | None, action: str = "view") -> bool:
    """See a live session and its case (``view``); warn/pause/resume/terminate it or decide the case (``update``)."""
    if can_manage_exams(auth):
        return True
    if test_owner_id is not None:
        return is_employer_member(auth) and auth.organization_id == test_owner_id
    return is_institution_staff(auth, action) and auth.organization_id == student_organization_id


def can_appeal(auth: AccessTokenClaims) -> bool:
    """A student appealing their own integrity decision: the Exam reviews page's Create cell."""
    return auth.can_act("exam_reviews.create", TAKE)


def can_decide_appeals(auth: AccessTokenClaims) -> bool:
    """An appeal goes above the first reviewer: the platform's exam managers only."""
    return can_manage_exams(auth)
