"""Who may do what with a ticket. One place, so the rules read the same everywhere they are applied.

  student                  their own tickets: open, read (never internal notes), reply, close, reopen, rate
  institution staff/head   the batch-staff queue of their own institution (a head may also assign within it)
  exams.manage             the exam-team (integrity) queue
  support.manage           every queue; assignment anywhere, SLA policies, platform canned replies, reports
  super admin              everything
"""

from app.core.security import AccessTokenClaims
from app.domain.enums import Queue
from app.models.ticket import Ticket
from app.permissions.roles import Role
from app.permissions.scopes import Scope


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def is_student(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.STUDENT


def is_institution_staff(auth: AccessTokenClaims) -> bool:
    return auth.role in {Role.STAFF, Role.INSTITUTION_HEAD} and auth.organization_id is not None


def is_manager(auth: AccessTokenClaims) -> bool:
    return is_super_admin(auth) or bool(auth.has_scope(Scope.SUPPORT_MANAGE.value))


def is_exam_team(auth: AccessTokenClaims) -> bool:
    return bool(auth.has_scope(Scope.EXAMS_MANAGE.value))


def can_handle(auth: AccessTokenClaims, ticket: Ticket) -> bool:
    """May act on ``ticket`` as an agent (read it with its internal notes, reply, change it)."""
    if is_manager(auth):
        return True
    if ticket.queue == Queue.EXAM_TEAM:
        return is_exam_team(auth)
    if ticket.queue == Queue.BATCH_STAFF:
        return is_institution_staff(auth) and auth.organization_id == ticket.organization_id
    return False


def can_view(auth: AccessTokenClaims, ticket: Ticket) -> bool:
    return auth.user_id == ticket.requester_user_id or can_handle(auth, ticket)


def can_assign_others(auth: AccessTokenClaims, ticket: Ticket) -> bool:
    if is_manager(auth):
        return True
    return auth.role == Role.INSTITUTION_HEAD and ticket.queue == Queue.BATCH_STAFF and auth.organization_id == ticket.organization_id


def is_agent(auth: AccessTokenClaims) -> bool:
    return is_manager(auth) or is_exam_team(auth) or is_institution_staff(auth)
