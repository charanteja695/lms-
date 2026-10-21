"""Authorization rules for the user hierarchy.

This module is the single source of truth for "who may do what to whom". It is pure
(no I/O) so every rule is unit-testable. Services load the data, then ask these
functions; they never re-implement a rule inline.

Checks happen in three layers:
  1. Role ceiling      - may this role ever perform ``action`` on users of ``target_role``? (``USER_PERMISSIONS``)
  2. Permission matrix - does this person hold the cell for it (``students.delete``)? A super admin ticks cells
                         per role and per person; see ``pages``.
  3. Resource scope    - is the target inside the actor's part of the hierarchy?
"""

from enum import StrEnum

from app.models.institution import Institution
from app.models.user import User
from app.permissions.pages import PEOPLE_PAGE
from app.permissions.roles import (
    ADMIN_SCOPES,
    ORGANIZATION_SCOPED_ROLES,
    ROLE_LEVELS,
    SCOPE_FOR_ORGANIZATION,
    AdminScope,
    OrganizationType,
    Role,
    organization_type_for,
    parse_role,
)


class Action(StrEnum):
    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    CHANGE_STATUS = "change_status"
    DELETE = "delete"
    REVOKE = "revoke"
    EXPORT = "export"


# Which matrix action each user action needs (suspending or reactivating someone is the Revoke cell).
_CELL_ACTION: dict[Action, str] = {
    Action.VIEW: "view",
    Action.CREATE: "create",
    Action.UPDATE: "update",
    Action.CHANGE_STATUS: "revoke",
    Action.DELETE: "delete",
    Action.REVOKE: "revoke",
    Action.EXPORT: "export",
}


def _all_actions(*roles: Role) -> dict[Action, frozenset[Role]]:
    return {action: frozenset(roles) for action in Action}


# actor role -> action -> target roles the actor may ever perform the action on (the ceiling); within it, the
# person's matrix cells decide.
USER_PERMISSIONS: dict[Role, dict[Action, frozenset[Role]]] = {
    Role.SUPER_ADMIN: {
        **_all_actions(
            Role.ADMIN, Role.INSTITUTION_HEAD, Role.STAFF, Role.STUDENT, Role.EMPLOYER_ADMIN, Role.RECRUITER
        ),
        # No new company logins: older ones can still be seen, edited, suspended or removed.
        Action.CREATE: frozenset({Role.ADMIN, Role.INSTITUTION_HEAD, Role.STAFF, Role.STUDENT}),
        Action.VIEW: frozenset(
            {
                Role.SUPER_ADMIN,
                Role.ADMIN,
                Role.INSTITUTION_HEAD,
                Role.STAFF,
                Role.STUDENT,
                Role.EMPLOYER_ADMIN,
                Role.RECRUITER,
            }
        ),
    },
    # Admins reach only members of organisations they own (see is_user_in_scope).
    Role.ADMIN: _all_actions(Role.INSTITUTION_HEAD, Role.STAFF, Role.STUDENT),
    Role.INSTITUTION_HEAD: _all_actions(Role.STAFF, Role.STUDENT),
    # What staff do to students by default is their matrix cells (view, create, update); more can be ticked.
    Role.STAFF: _all_actions(Role.STUDENT),
    Role.STUDENT: {},
    Role.EMPLOYER_ADMIN: {},
    Role.RECRUITER: {},
}


# ------------------------------------------------------------------ role permission


def holds(actor: User, cell: str) -> bool:
    """Whether ``actor`` holds a matrix cell (``staff.create``). A super admin holds everything."""
    return actor.role == Role.SUPER_ADMIN or cell in actor.granted


def _cell_allows(actor: User, action: Action, target: Role) -> bool:
    page = PEOPLE_PAGE.get(target)
    if actor.role == Role.SUPER_ADMIN or page is None:
        return True  # only the super admin reaches roles without a matrix page (admins, company logins)
    return holds(actor, f"{page}.{_CELL_ACTION[action]}")


def allowed_target_roles(actor: User, action: Action) -> frozenset[Role]:
    role = parse_role(actor.role)
    if role is None:
        return frozenset()
    ceiling = USER_PERMISSIONS.get(role, {}).get(action, frozenset())
    return frozenset(target for target in ceiling if _cell_allows(actor, action, target))


def can_act_on_role(actor: User, action: Action, target_role: str) -> bool:
    target = parse_role(target_role)
    return target is not None and target in allowed_target_roles(actor, action)


def is_organization_scoped(role: str) -> bool:
    parsed = parse_role(role)
    return parsed is not None and parsed in ORGANIZATION_SCOPED_ROLES


def is_valid_manager(manager_role: str, subordinate_role: str) -> bool:
    """A manager must belong to the same kind of organisation and rank strictly above the subordinate."""
    manager, subordinate = parse_role(manager_role), parse_role(subordinate_role)
    if manager is None or subordinate is None:
        return False
    return (
        manager in ORGANIZATION_SCOPED_ROLES
        and organization_type_for(manager) == organization_type_for(subordinate)
        and ROLE_LEVELS[manager] > ROLE_LEVELS[subordinate]
    )


# ------------------------------------------------------------------ admin scopes


def has_scope(actor: User, scope: AdminScope) -> bool:
    if actor.role == Role.SUPER_ADMIN:
        return True
    return actor.role == Role.ADMIN and scope in ADMIN_SCOPES and scope in actor.scope_list


def token_scopes(user: User) -> list[str]:
    """Scopes carried in the access token: every scope for super admins, assigned scopes for admins."""
    if user.role == Role.SUPER_ADMIN:
        return [scope.value for scope in AdminScope]
    return [scope for scope in user.scope_list if scope in ADMIN_SCOPES] if user.role == Role.ADMIN else []


# ------------------------------------------------------------------ resource scope


def can_access_institution(actor: User, institution: Institution) -> bool:
    """Read access to an institution (and the users inside it)."""
    if actor.role == Role.SUPER_ADMIN:
        return True
    if institution.deleted_at is not None:
        return False
    if actor.role == Role.ADMIN:
        return institution.admin_id == actor.id
    return actor.institution_id is not None and actor.institution_id == institution.id


def _kind(institution: Institution) -> OrganizationType:
    return (
        OrganizationType.EMPLOYER if institution.org_type == OrganizationType.EMPLOYER else OrganizationType.INSTITUTION
    )


def _institution_cell(actor: User, org_type: OrganizationType, action: str) -> bool:
    """An admin's institutions are on the matrix (members see their own institution regardless); companies belong
    to the super admin alone."""
    return (
        actor.role != Role.ADMIN or org_type != OrganizationType.INSTITUTION or holds(actor, f"institutions.{action}")
    )


def can_create_organization(actor: User, org_type: OrganizationType) -> bool:
    return (
        actor.role in (Role.SUPER_ADMIN, Role.ADMIN)
        and has_scope(actor, SCOPE_FOR_ORGANIZATION[org_type])
        and _institution_cell(actor, org_type, "create")
    )


def can_create_institution(actor: User) -> bool:
    return can_create_organization(actor, OrganizationType.INSTITUTION)


def owns_institution(actor: User, institution: Institution) -> bool:
    """The super admin, or the admin who owns it (and so keeps its academic structure)."""
    if actor.role == Role.SUPER_ADMIN:
        return True
    return actor.role == Role.ADMIN and institution.deleted_at is None and institution.admin_id == actor.id


def can_manage_institution(actor: User, institution: Institution, action: str = "update") -> bool:
    """Update, suspend/reactivate/sign out (``revoke``) or delete an institution: its owner, holding that cell."""
    return owns_institution(actor, institution) and _institution_cell(actor, _kind(institution), action)


def can_see_organizations(actor: User, org_type: OrganizationType) -> bool:
    return (
        actor.role in (Role.SUPER_ADMIN, Role.ADMIN)
        and has_scope(actor, SCOPE_FOR_ORGANIZATION[org_type])
        and _institution_cell(actor, org_type, "view")
    )


def can_list_organizations(actor: User, org_type: OrganizationType, action: str = "view") -> bool:
    """See (or, with ``export``, download) the institution list; an admin needs those cells."""
    return _institution_cell(actor, org_type, "view") and _institution_cell(actor, org_type, action)


def can_export_organizations(actor: User, org_type: OrganizationType) -> bool:
    return can_see_organizations(actor, org_type) and _institution_cell(actor, org_type, "export")


def can_reassign_institution_admin(actor: User) -> bool:
    return actor.role == Role.SUPER_ADMIN


def is_user_in_scope(actor: User, target: User, target_institution: Institution | None) -> bool:
    if actor.role == Role.SUPER_ADMIN:
        return True
    if target_institution is None or target.institution_id != target_institution.id:
        # Unscoped users (admins, super admins) are only reachable by super admins.
        return False
    return can_access_institution(actor, target_institution)
