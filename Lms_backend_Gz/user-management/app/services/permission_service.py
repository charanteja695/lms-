"""Role- and person-level permissions: read them, and let a super admin change them.

A change never signs anyone out: it makes the affected access tokens refresh, and the new token carries the new
permissions. One person → their token version goes up (``access.user_revoked``, sessions kept). A whole role →
``access.role_revoked``, which every service applies to that role's tokens issued before now.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_state import ROLE_REVOKED, USER_REVOKED
from app.core.context import RequestContext
from app.core.exceptions import PermissionDeniedError, ValidationFailedError
from app.db.types import uuid7
from app.domain.enums import InstitutionType
from app.models.institution import Institution
from app.models.outbox_event import OutboxEvent
from app.models.permission import RolePermission, UserPermission
from app.models.user import User
from app.permissions.effective import effective, role_defaults
from app.permissions.features import BY_KEY, PERMISSIONS, eligible
from app.permissions.pages import MATRIX_ROLES, PAGES, cell_defaults, may_hold, split
from app.permissions.roles import ADMIN_SCOPES, Role, organization_type_for
from app.services.audit_service import AuditAction, AuditService

# Roles whose defaults a super admin edits (an admin's platform scopes are their own, per person).
EDITABLE_ROLES: tuple[Role, ...] = (
    Role.ADMIN,
    Role.INSTITUTION_HEAD,
    Role.STAFF,
    Role.STUDENT,
    Role.EMPLOYER_ADMIN,
    Role.RECRUITER,
)


def _org_type(role: Role) -> str | None:
    kind = organization_type_for(role)
    return kind.value if kind else None


def _unknown(key: str) -> ValidationFailedError:
    return ValidationFailedError(
        details=[{"field": key, "code": "UNKNOWN_PERMISSION", "message": "No such permission"}]
    )


def _not_for(key: str, role: Role) -> ValidationFailedError:
    return ValidationFailedError(
        details=[
            {
                "field": key,
                "code": "NOT_FOR_THIS_ROLE",
                "message": f"A {role.value.replace('_', ' ')} cannot hold this permission",
            }
        ]
    )


def _keys_for(role: Role) -> list[str]:
    """What can be ticked for ``role``: matrix cells (in page and action order), or the older feature keys."""
    if role in MATRIX_ROLES:
        return [f"{p.key}.{a}" for p in PAGES if role in p.holders for a in p.actions]
    return [p.key for p in PERMISSIONS if eligible(p, role, _org_type(role))]


def _catalog_defaults(role: Role) -> set[str]:
    return cell_defaults(role) if role in MATRIX_ROLES else {p.key for p in PERMISSIONS if role in p.default_roles}


def _check(key: str, role: Role, *, scopes: bool = False) -> None:
    """``scopes``: an admin's platform scopes may be changed too (per person only)."""
    if role in MATRIX_ROLES:
        if may_hold(key, role) or (scopes and role == Role.ADMIN and key in ADMIN_SCOPES):
            return
        raise _not_for(key, role) if key in BY_KEY or split(key) else _unknown(key)
    permission = BY_KEY.get(key)
    if permission is None:
        raise _unknown(key)
    if not eligible(permission, role, _org_type(role)):
        raise _not_for(key, role)


class PermissionService:
    def __init__(self, db: AsyncSession, ctx: RequestContext | None = None) -> None:
        self.db = db
        self.audit = AuditService(db, ctx) if ctx else None

    # ------------------------------------------------------------------ reading
    async def role_overrides(self, role: Role) -> dict[str, bool]:
        rows = (await self.db.execute(select(RolePermission).where(RolePermission.role == role.value))).scalars()
        return {r.permission: r.allowed for r in rows}

    async def user_overrides(self, user: User) -> dict[str, bool]:
        rows = (await self.db.execute(select(UserPermission).where(UserPermission.user_id == user.id))).scalars()
        return {r.permission: r.allowed for r in rows}

    async def effective_for(self, user: User) -> list[str]:
        role = Role(user.role)
        individual = (
            role == Role.STUDENT
            and user.institution_id is not None
            and (
                await self.db.scalar(select(Institution.institution_type).where(Institution.id == user.institution_id))
            )
            == InstitutionType.INDIVIDUAL
        )
        return effective(
            role,
            _org_type(role),
            admin_scopes=user.scope_list,
            role_overrides=await self.role_overrides(role),
            user_overrides=await self.user_overrides(user),
            individual=individual,
        )

    async def role_matrix(self) -> list[dict[str, Any]]:
        """For each editable role: everything it may hold, whether it holds it, and whether that differs from the catalog."""
        out = []
        for role in EDITABLE_ROLES:
            overrides = await self.role_overrides(role)
            held = role_defaults(role, overrides)
            out.append(
                {
                    "role": role.value,
                    "permissions": [
                        {"key": k, "allowed": k in held, "changed": k in overrides} for k in _keys_for(role)
                    ],
                }
            )
        return out

    async def user_view(self, user: User) -> dict[str, Any]:
        """Everything this person may hold: from their role, their own grant/removal, and the result.

        An admin's rows are their matrix cells followed by their platform scopes (which are theirs alone)."""
        role = Role(user.role)
        if role == Role.SUPER_ADMIN:
            return {
                "editable": False,
                "permissions": [
                    {"key": k, "from_role": True, "override": None, "allowed": True} for k in sorted(BY_KEY)
                ],
            }
        from_role = role_defaults(role, await self.role_overrides(role))
        overrides = await self.user_overrides(user)
        result = set(await self.effective_for(user))
        rows = [
            {"key": k, "from_role": k in from_role, "override": overrides.get(k), "allowed": k in result}
            for k in _keys_for(role)
        ]
        if role == Role.ADMIN:
            scopes = set(user.scope_list)
            rows += [
                {"key": str(s), "from_role": False, "override": str(s) in scopes, "allowed": str(s) in result}
                for s in ADMIN_SCOPES
            ]
        return {"editable": True, "permissions": rows}

    # ------------------------------------------------------------------ changing
    async def set_role(self, actor: User, role: Role, changes: dict[str, bool | None]) -> None:
        """``True``/``False`` set the role's default; ``None`` restores the catalog's."""
        if role not in EDITABLE_ROLES:
            raise ValidationFailedError(
                details=[
                    {"field": "role", "code": "NOT_EDITABLE", "message": "Only member roles have editable defaults"}
                ]
            )
        for key in changes:
            _check(key, role)
        catalog = _catalog_defaults(role)
        for key, allowed in changes.items():
            await self.db.execute(
                delete(RolePermission).where(RolePermission.role == role.value, RolePermission.permission == key)
            )
            if allowed is not None and allowed != (key in catalog):
                self.db.add(
                    RolePermission(id=uuid7(), role=role.value, permission=key, allowed=allowed, changed_by=actor.id)
                )
        self._event(
            ROLE_REVOKED, "role", actor.id, {"role": role.value, "revoked_at": int(datetime.now(UTC).timestamp())}
        )
        if self.audit:
            self.audit.log(
                AuditAction.ROLE_PERMISSIONS_CHANGED,
                actor_id=actor.id,
                resource_type="role",
                details={"role": role.value, "changes": changes},
            )
        await self.db.commit()

    async def set_user(self, actor: User, target: User, changes: dict[str, bool | None], reason: str | None) -> None:
        """Grant (``True``), remove (``False``) or restore the role's setting (``None``) for one person.

        An admin's platform scopes are theirs alone, so for those keys this edits the scopes themselves.
        """
        role = Role(target.role)
        if role == Role.SUPER_ADMIN:
            raise PermissionDeniedError("A super admin always holds every permission.")
        for key in changes:
            _check(key, role, scopes=True)
        if role == Role.ADMIN:
            scopes = set(target.scope_list)
            for key, allowed in changes.items():
                if key in ADMIN_SCOPES:
                    (scopes.add if allowed else scopes.discard)(key)
            target.set_scopes(sorted(scopes))
        defaults = role_defaults(role, await self.role_overrides(role))
        for key, allowed in changes.items():
            if role == Role.ADMIN and key in ADMIN_SCOPES:
                continue
            await self.db.execute(
                delete(UserPermission).where(UserPermission.user_id == target.id, UserPermission.permission == key)
            )
            if allowed is not None and allowed != (key in defaults):
                self.db.add(
                    UserPermission(
                        id=uuid7(),
                        user_id=target.id,
                        permission=key,
                        allowed=allowed,
                        reason=reason,
                        changed_by=actor.id,
                    )
                )
        target.token_version += 1
        self._event(
            USER_REVOKED,
            "user",
            target.id,
            {"user_id": str(target.public_id), "token_version": target.token_version, "reason": "permissions_changed"},
        )
        if self.audit:
            self.audit.log(
                AuditAction.USER_PERMISSIONS_CHANGED,
                actor_id=actor.id,
                resource_type="user",
                resource_id=target.id,
                institution_id=target.institution_id,
                details={"changes": changes, "reason": reason},
            )
        await self.db.commit()

    def _event(self, event_type: str, aggregate_type: str, aggregate_id: Any, payload: dict[str, Any]) -> None:
        self.db.add(
            OutboxEvent(
                id=uuid7(),
                event_type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                payload=payload,
            )
        )
