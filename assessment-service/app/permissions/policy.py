"""Who may do what. One place, so the rules read the same everywhere they are applied.

Ownership: a question or test belongs to the platform (``owner_organization_id`` is None) or to one employer
(hiring assessments). Platform content is written and reviewed with the ``content.author`` / ``content.review``
scopes; an employer's own content by its members. A test only ever uses questions of its own owner.
"""

from app.core.security import AccessTokenClaims
from app.permissions.roles import Role
from app.permissions.scopes import Scope

_EMPLOYER_ROLES = frozenset({Role.EMPLOYER_ADMIN, Role.RECRUITER})
_INSTITUTION_STAFF_ROLES = frozenset({Role.STAFF, Role.INSTITUTION_HEAD})


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def is_student(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.STUDENT


def is_employer_member(auth: AccessTokenClaims) -> bool:
    return auth.role in _EMPLOYER_ROLES and auth.organization_id is not None


def is_institution_staff(auth: AccessTokenClaims) -> bool:
    return auth.role in _INSTITUTION_STAFF_ROLES and auth.organization_id is not None


def can_manage_exams(auth: AccessTokenClaims) -> bool:
    """Schedule exams, grade any attempt, run live attempts, decide on regrades and result release."""
    return is_super_admin(auth) or auth.has_scope(Scope.EXAMS_MANAGE.value)


def can_author_platform(auth: AccessTokenClaims) -> bool:
    return is_super_admin(auth) or auth.has_scope(Scope.CONTENT_AUTHOR.value)


def can_review_platform(auth: AccessTokenClaims) -> bool:
    return is_super_admin(auth) or auth.has_scope(Scope.CONTENT_REVIEW.value)


def author_organization(auth: AccessTokenClaims) -> tuple[bool, int | None]:
    """(may author, the owner organisation new content gets): platform authors own platform content, employer
    members their employer's."""
    if can_author_platform(auth):
        return True, None
    if is_employer_member(auth):
        return True, auth.organization_id
    return False, None


def can_author(auth: AccessTokenClaims) -> bool:
    return author_organization(auth)[0]


def can_author_owned_by(auth: AccessTokenClaims, owner_organization_id: int | None) -> bool:
    if owner_organization_id is None:
        return can_author_platform(auth)
    return is_super_admin(auth) or (is_employer_member(auth) and auth.organization_id == owner_organization_id)


def can_review_owned_by(auth: AccessTokenClaims, owner_organization_id: int | None) -> bool:
    """Approve, reject, retire; see answer keys. An employer's admin reviews the employer's own content."""
    if owner_organization_id is None:
        return can_review_platform(auth)
    return is_super_admin(auth) or (auth.role == Role.EMPLOYER_ADMIN and auth.organization_id == owner_organization_id)


def can_read_owned_by(auth: AccessTokenClaims, owner_organization_id: int | None) -> bool:
    """Read questions/tests with their keys (authors, reviewers and exam managers of the owner)."""
    if owner_organization_id is None:
        return can_author_platform(auth) or can_review_platform(auth) or can_manage_exams(auth)
    return is_super_admin(auth) or (is_employer_member(auth) and auth.organization_id == owner_organization_id)


def can_manage_owned_by(auth: AccessTokenClaims, owner_organization_id: int | None) -> bool:
    """Schedules, invitations, result release and reports for a test."""
    if owner_organization_id is None:
        return can_manage_exams(auth)
    return is_super_admin(auth) or (is_employer_member(auth) and auth.organization_id == owner_organization_id)


def can_view_attempt(
    auth: AccessTokenClaims, *, attempt_user_id: int, attempt_organization_id: int | None, test_owner_id: int | None
) -> bool:
    """The student, exam managers and reviewers, the student's own institution staff, or the employer that owns a
    hiring assessment."""
    if auth.user_id == attempt_user_id:
        return True
    if can_manage_exams(auth) or can_review_platform(auth):
        return True
    # Institution staff see their own students' attempts on platform tests; an employer's hiring assessment is private
    # to that employer and the candidate, even from the candidate's own institution.
    if is_institution_staff(auth) and test_owner_id is None and auth.organization_id == attempt_organization_id:
        return True
    return test_owner_id is not None and can_manage_owned_by(auth, test_owner_id)


def can_grade_attempt(
    auth: AccessTokenClaims, *, attempt_organization_id: int | None, test_owner_id: int | None
) -> bool:
    """Grade subjective/file answers and run live controls (pause, terminate). Institution staff act on their own
    students' attempts of platform tests; a hiring assessment is its employer's to grade."""
    if can_manage_exams(auth):
        return True
    if test_owner_id is not None:
        return can_manage_owned_by(auth, test_owner_id)
    return is_institution_staff(auth) and auth.organization_id == attempt_organization_id
