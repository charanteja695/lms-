"""Who may do what with a ticket, as permissions from the access token (user-management's catalog; a super admin can
grant or remove any of them per person). One place, so the rules read the same everywhere they are applied.

  support.ask              their own tickets: open, read (never internal notes), reply, close, reopen, rate (a student)
  support.agent            the batch-staff queue of their own institution (staff, head)
  support.assign           assign within that queue (a head)
  exams.manage             the exam-team (integrity) queue
  support.manage           every queue; assignment anywhere, SLA policies, platform canned replies, reports
  super admin              everything
"""

from app.core.security import AccessTokenClaims
from app.domain.enums import Queue
from app.models.ticket import Ticket
from app.permissions.roles import Role
from app.permissions.scopes import Scope

# What a person needs to handle (and so be assigned) a ticket of each queue; mirrors ``can_handle``.
HANDLER_PERMISSIONS: dict[Queue, tuple[str, ...]] = {
    Queue.BATCH_STAFF: ("support_queue.update",),  # whoever may answer that queue (a matrix cell)
    Queue.EXAM_TEAM: (Scope.EXAMS_MANAGE.value, Scope.SUPPORT_MANAGE.value),
    Queue.PLATFORM_SUPPORT: (Scope.SUPPORT_MANAGE.value,),
}


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def is_student(auth: AccessTokenClaims, action: str = "view") -> bool:
    """Their own tickets (the Help page's cells): ``view`` read and follow them, ``create`` open one."""
    return auth.role != Role.SUPER_ADMIN and auth.can_act(f"support.{action}", "support.ask")


def is_institution_staff(auth: AccessTokenClaims, action: str = "view") -> bool:
    """Their own institution's batch-staff queue (the Support queue page's cells): ``view`` read, ``update`` answer
    and change tickets."""
    return auth.organization_id is not None and auth.can_act(f"support_queue.{action}", "support.agent")


def is_manager(auth: AccessTokenClaims) -> bool:
    return auth.can(Scope.SUPPORT_MANAGE.value)


def manages_ticket(auth: AccessTokenClaims, ticket: Ticket) -> bool:
    """A support manager: the super admin for every ticket, an admin for tickets from the institutions they look after."""
    if not is_manager(auth):
        return False
    care = auth.organizations_in_care()
    return care is None or ticket.organization_id in care


def is_exam_team(auth: AccessTokenClaims) -> bool:
    return bool(auth.has_scope(Scope.EXAMS_MANAGE.value))


def can_handle(auth: AccessTokenClaims, ticket: Ticket, action: str = "view") -> bool:
    """May read ``ticket`` with its internal notes (``view``) or reply and change it (``update``) as an agent."""
    if manages_ticket(auth, ticket):
        return True
    if ticket.queue == Queue.EXAM_TEAM:
        return is_exam_team(auth)
    if ticket.queue == Queue.BATCH_STAFF:
        return is_institution_staff(auth, action) and auth.organization_id == ticket.organization_id
    return False


def can_view(auth: AccessTokenClaims, ticket: Ticket) -> bool:
    return auth.user_id == ticket.requester_user_id or can_handle(auth, ticket)


def can_assign_others(auth: AccessTokenClaims, ticket: Ticket) -> bool:
    if manages_ticket(auth, ticket):
        return True
    return auth.can_act("support_queue.approve", "support.assign") and ticket.queue == Queue.BATCH_STAFF and auth.organization_id == ticket.organization_id


def is_agent(auth: AccessTokenClaims) -> bool:
    return is_manager(auth) or is_exam_team(auth) or is_institution_staff(auth)
