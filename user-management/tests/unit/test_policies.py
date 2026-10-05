import uuid

import pytest

from app.models import Institution, User
from app.permissions import policies
from app.permissions.policies import Action
from app.permissions.roles import Role


def _user(role: Role, institution_id: uuid.UUID | None = None) -> User:
    return User(id=uuid.uuid4(), role=role, institution_id=institution_id)


def _institution(admin_id: uuid.UUID) -> Institution:
    return Institution(id=uuid.uuid4(), admin_id=admin_id, deleted_at=None)


@pytest.mark.parametrize(
    ("actor", "target", "allowed"),
    [
        (Role.SUPER_ADMIN, Role.ADMIN, True),
        (Role.SUPER_ADMIN, Role.SUPER_ADMIN, False),
        (Role.ADMIN, Role.ADMIN, False),
        (Role.ADMIN, Role.INSTITUTION_HEAD, True),
        (Role.INSTITUTION_HEAD, Role.INSTITUTION_HEAD, False),
        (Role.INSTITUTION_HEAD, Role.STAFF, True),
        (Role.STAFF, Role.STAFF, False),
        (Role.STAFF, Role.STUDENT, True),
        (Role.STUDENT, Role.STUDENT, False),
    ],
)
def test_create_permissions(actor: Role, target: Role, allowed: bool) -> None:
    assert policies.can_act_on_role(actor, Action.CREATE, target) is allowed


def test_no_role_can_act_on_its_own_level_or_above() -> None:
    from app.permissions.roles import ROLE_LEVELS

    for actor, actions in policies.USER_PERMISSIONS.items():
        for action, targets in actions.items():
            if action == Action.VIEW:
                continue
            for target in targets:
                assert ROLE_LEVELS[target] < ROLE_LEVELS[actor], (actor, action, target)


def test_staff_has_limited_actions() -> None:
    for action in (Action.DELETE, Action.CHANGE_STATUS, Action.REVOKE):
        assert not policies.can_act_on_role(Role.STAFF, action, Role.STUDENT)


def test_unknown_roles_get_nothing() -> None:
    assert policies.allowed_target_roles("janitor", Action.VIEW) == frozenset()
    assert not policies.can_act_on_role(Role.SUPER_ADMIN, Action.VIEW, "janitor")


def test_institution_scope() -> None:
    admin = _user(Role.ADMIN)
    other_admin = _user(Role.ADMIN)
    owned, foreign = _institution(admin.id), _institution(other_admin.id)
    head = _user(Role.INSTITUTION_HEAD, owned.id)

    assert policies.can_access_institution(admin, owned)
    assert not policies.can_access_institution(admin, foreign)
    assert policies.can_access_institution(head, owned)
    assert not policies.can_access_institution(head, foreign)
    assert policies.can_manage_institution(admin, owned)
    assert not policies.can_manage_institution(head, owned)
    assert policies.can_access_institution(_user(Role.SUPER_ADMIN), foreign)


def test_unscoped_users_only_reachable_by_super_admin() -> None:
    admin = _user(Role.ADMIN)
    target_admin = _user(Role.ADMIN)
    assert not policies.is_user_in_scope(admin, target_admin, None)
    assert policies.is_user_in_scope(_user(Role.SUPER_ADMIN), target_admin, None)


def test_manager_rules() -> None:
    assert policies.is_valid_manager(Role.INSTITUTION_HEAD, Role.STAFF)
    assert policies.is_valid_manager(Role.STAFF, Role.STUDENT)
    assert not policies.is_valid_manager(Role.STAFF, Role.STAFF)
    assert not policies.is_valid_manager(Role.ADMIN, Role.INSTITUTION_HEAD)
