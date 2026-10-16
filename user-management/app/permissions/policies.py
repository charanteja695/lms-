"""Authorization rules for the user hierarchy.

This module is the single source of truth for "who may do what to whom". It is pure
(no I/O) so every rule is unit-testable. Services load the data, then ask these
functions; they never re-implement a rule inline.

Checks happen in two layers:
  1. Role permission   - may this role perform ``action`` on users of ``target_role``?
  2. Resource scope    - is the target inside the actor's part of the hierarchy?
"""

from enum import StrEnum

from app.models.institution import Institution
from app.models.user import User
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


def _all_actions(*roles: Role) -> dict[Action, frozenset[Role]]:
    return {action: frozenset(roles) for action in Action}


# actor role -> action -> target roles the actor may perform the action on.
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
    Role.STAFF: {
        Action.VIEW: frozenset({Role.STUDENT}),
        Action.CREATE: frozenset({Role.STUDENT}),
        Action.UPDATE: frozenset({Role.STUDENT}),
    },
    Role.STUDENT: {},
    Role.EMPLOYER_ADMIN: {},
    Role.RECRUITER: {},
}


# ------------------------------------------------------------------ role permission


def allowed_target_roles(actor_role: str, action: Action) -> frozenset[Role]:
    role = parse_role(actor_role)
    if role is None:
        return frozenset()
    return USER_PERMISSIONS.get(role, {}).get(action, frozenset())


def can_act_on_role(actor_role: str, action: Action, target_role: str) -> bool:
    target = parse_role(target_role)
    return target is not None and target in allowed_target_roles(actor_role, action)


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


def can_create_organization(actor: User, org_type: OrganizationType) -> bool:
    return actor.role in (Role.SUPER_ADMIN, Role.ADMIN) and has_scope(actor, SCOPE_FOR_ORGANIZATION[org_type])


def can_create_institution(actor: User) -> bool:
    return can_create_organization(actor, OrganizationType.INSTITUTION)


def can_manage_institution(actor: User, institution: Institution) -> bool:
    """Update, suspend, delete or revoke an institution."""
    if actor.role == Role.SUPER_ADMIN:
        return True
    return actor.role == Role.ADMIN and institution.deleted_at is None and institution.admin_id == actor.id


def can_reassign_institution_admin(actor: User) -> bool:
    return actor.role == Role.SUPER_ADMIN


def is_user_in_scope(actor: User, target: User, target_institution: Institution | None) -> bool:
    if actor.role == Role.SUPER_ADMIN:
        return True
    if target_institution is None or target.institution_id != target_institution.id:
        # Unscoped users (admins, super admins) are only reachable by super admins.
        return False
    return can_access_institution(actor, target_institution)
