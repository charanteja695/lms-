"""A person's effective permissions, from the catalog's defaults and the stored differences (pure, no I/O)."""

from collections.abc import Iterable, Mapping

from app.permissions.features import BY_KEY, MENU, MODULES, PERMISSIONS, PLATFORM_KEYS, eligible
from app.permissions.roles import Role


def role_defaults(role: Role, role_overrides: Mapping[str, bool]) -> set[str]:
    """What everyone with ``role`` holds: the catalog's defaults, with a super admin's changes to that role applied."""
    held = {p.key for p in PERMISSIONS if role in p.default_roles}
    for key, allowed in role_overrides.items():
        (held.add if allowed else held.discard)(key)
    return held


def effective(
    role: Role,
    organization_type: str | None,
    *,
    admin_scopes: Iterable[str],
    role_overrides: Mapping[str, bool],
    user_overrides: Mapping[str, bool],
) -> list[str]:
    """Role defaults + an admin's scopes + this person's grants − their removals, limited to what the role may hold.

    A super admin gets every platform permission listed (and every service treats them as holding everything).
    """
    if role == Role.SUPER_ADMIN:
        return sorted(PLATFORM_KEYS)
    held = role_defaults(role, role_overrides)
    if role == Role.ADMIN:
        held |= set(admin_scopes)
    for key, allowed in user_overrides.items():
        (held.add if allowed else held.discard)(key)
    return sorted(k for k in held if k in BY_KEY and eligible(BY_KEY[k], role, organization_type))


def modules_for(permissions: Iterable[str]) -> list[str]:
    """The other services' menu modules these permissions open (in menu order); everyone has notifications."""
    opened = {m for key in permissions if key in BY_KEY for m in BY_KEY[key].modules} | {"notifications"}
    return [m for m in MODULES if m in opened]


def menu_for(permissions: Iterable[str]) -> list[str]:
    """Feature-level menu entries these permissions open (in menu order)."""
    held = set(permissions)
    return [entry for entry, needs in MENU.items() if held & {str(n) for n in needs}]
