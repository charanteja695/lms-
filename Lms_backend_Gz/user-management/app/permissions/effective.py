"""A person's effective permissions, from the catalog's defaults and the stored differences (pure, no I/O).

Admins, institution heads, staff and students are set on the permission matrix (``pages``): they hold cells
(``students.delete``), and each cell brings the older feature keys it implies, which the other services check.
Older company roles (employer admin, recruiter) still hold feature keys directly.
"""

from collections.abc import Iterable, Mapping

from app.permissions.features import BY_KEY, MENU, MODULES, PERMISSIONS, PLATFORM_KEYS, eligible
from app.permissions.pages import CELL_KEYS, MATRIX_ROLES, cell_defaults, implied, may_hold, without_orphans
from app.permissions.roles import ADMIN_SCOPES, Role

STORE_BUY = "store.buy"
STUDENT_PAYMENT_REQUEST = "student.payment_request"
INSTITUTION_PAYMENTS_MANAGE = "institution.payments.manage"


def _apply(held: set[str], overrides: Mapping[str, bool], keep: Iterable[str] | None = None) -> set[str]:
    allowed_keys = set(keep) if keep is not None else None
    for key, allowed in overrides.items():
        if allowed_keys is None or key in allowed_keys:
            (held.add if allowed else held.discard)(key)
    return held


def role_defaults(role: Role, role_overrides: Mapping[str, bool]) -> set[str]:
    """What everyone with ``role`` holds before person changes: the catalog's defaults with a super admin's changes.

    Matrix roles hold cells; the older company roles hold feature keys.
    """
    if role in MATRIX_ROLES:
        return {c for c in _apply(cell_defaults(role), role_overrides, CELL_KEYS) if may_hold(c, role)}
    return _apply({p.key for p in PERMISSIONS if role in p.default_roles}, role_overrides)


def effective(
    role: Role,
    organization_type: str | None,
    *,
    admin_scopes: Iterable[str],
    role_overrides: Mapping[str, bool],
    user_overrides: Mapping[str, bool],
    individual: bool = False,
) -> list[str]:
    """Role defaults + this person's grants − their removals, limited to what the role may hold.

    Matrix roles: the cells held (a page's other actions only while its View is held) plus the feature keys they
    imply; an admin adds their platform scopes. Students also hold store/subscription capabilities so they can
    browse approved courses and manage their subscriptions. A super admin gets every platform permission listed
    (and every service treats them as holding everything).
    """
    if role == Role.SUPER_ADMIN:
        return sorted(PLATFORM_KEYS)
    if role in MATRIX_ROLES:
        cells = without_orphans(
            {c for c in _apply(role_defaults(role, role_overrides), user_overrides, CELL_KEYS) if may_hold(c, role)}
        )
        extra = {s for s in admin_scopes if s in ADMIN_SCOPES} if role == Role.ADMIN else implied(cells)
        if role == Role.STUDENT:
            if individual:
                extra.add(STORE_BUY)
        elif role == Role.INSTITUTION_HEAD:
            extra.add(INSTITUTION_PAYMENTS_MANAGE)
        return sorted(cells | extra)
    held = _apply(role_defaults(role, role_overrides), user_overrides)
    return sorted(k for k in held if k in BY_KEY and eligible(BY_KEY[k], role, organization_type))


def modules_for(permissions: Iterable[str]) -> list[str]:
    """The other services' menu modules these permissions open (in menu order); everyone has notifications."""
    opened = {m for key in permissions if key in BY_KEY for m in BY_KEY[key].modules} | {"notifications"}
    return [m for m in MODULES if m in opened]


def menu_for(permissions: Iterable[str]) -> list[str]:
    """Feature-level menu entries these permissions open (in menu order)."""
    held = set(permissions)
    return [entry for entry, needs in MENU.items() if held & {str(n) for n in needs}]
