"""Who may do what, as permissions from the access token (user-management's catalog; a super admin can grant or
remove any of them per person). One place, so the rules read the same everywhere they are applied.

  tutor.chat                 talk to the tutor (by default a student; never implied by being a super admin)
  tutor.faq.manage           their own institution's FAQ (by default staff and head)
  tutor.conversations.view   read their own institution's students' tutor conversations (by default staff and head)
  content.author             a course's FAQ, evaluation sets and feedback
  support.manage             every FAQ, escalation and conversation
  ai.manage                  the search index
"""

from app.core.security import AccessTokenClaims
from app.domain.enums import FaqScope
from app.permissions.roles import Role
from app.permissions.scopes import Scope

CHAT = "tutor.chat"
FAQ_MANAGE = "tutor.faq.manage"
CONVERSATIONS_VIEW = "tutor.conversations.view"


def is_super_admin(auth: AccessTokenClaims) -> bool:
    return auth.role == Role.SUPER_ADMIN


def is_student(auth: AccessTokenClaims) -> bool:
    """May talk to the tutor."""
    return auth.has_scope(CHAT)


def is_institution_staff(auth: AccessTokenClaims, action: str = "view") -> bool:
    """Their own institution's FAQ, one action at a time (the Tutor FAQ page's cells: view, create, update, delete)."""
    return auth.organization_id is not None and auth.can_act(f"tutor_faq.{action}", FAQ_MANAGE)


def can_manage_support(auth: AccessTokenClaims) -> bool:
    """Every FAQ, every escalation, any conversation's transcript."""
    return auth.can(Scope.SUPPORT_MANAGE.value)


def can_author(auth: AccessTokenClaims) -> bool:
    """Course authors: a course's FAQ, its evaluation sets and its feedback."""
    return auth.can(Scope.CONTENT_AUTHOR.value)


def can_manage_index(auth: AccessTokenClaims) -> bool:
    return auth.can(Scope.AI_MANAGE.value)


def can_manage_faq(auth: AccessTokenClaims, scope: str, *, organization_id: int | None, action: str = "update") -> bool:
    """``action``: create, update (edit or publish) or delete (archive) — checked per cell for an institution's FAQ."""
    if can_manage_support(auth):
        return True
    if scope == FaqScope.COURSE:
        return can_author(auth)
    if scope == FaqScope.ORGANIZATION:
        return is_institution_staff(auth, action) and auth.organization_id == organization_id
    return False


def can_view_conversation(auth: AccessTokenClaims, *, organization_id: int | None) -> bool:
    """A support manager, or the staff/head of the student's own institution (to promote a good answer to the FAQ)."""
    return can_manage_support(auth) or (organization_id is not None and auth.organization_id == organization_id and auth.can_act("tutor_chats.view", CONVERSATIONS_VIEW))
