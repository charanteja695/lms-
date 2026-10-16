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
from app.models.outbox_event import OutboxEvent
from app.models.permission import RolePermission, UserPermission
from app.models.user import User
from app.permissions.effective import effective, role_defaults
from app.permissions.features import BY_KEY, PERMISSIONS, eligible
from app.permissions.roles import Role, organization_type_for
from app.services.audit_service import AuditAction, AuditService

# Roles whose defaults a super admin edits (an admin's platform permissions are their own, per person).
EDITABLE_ROLES: tuple[Role, ...] = (
    Role.INSTITUTION_HEAD,
    Role.STAFF,
    Role.STUDENT,
    Role.EMPLOYER_ADMIN,
    Role.RECRUITER,
)


def _org_type(role: Role) -> str | None:
    kind = organization_type_for(role)
    return kind.value if kind else None


def _check(key: str, role: Role) -> None:
    permission = BY_KEY.get(key)
    if permission is None:
        raise ValidationFailedError(
            details=[{"field": key, "code": "UNKNOWN_PERMISSION", "message": "No such permission"}]
        )
    if not eligible(permission, role, _org_type(role)):
        raise ValidationFailedError(
            details=[
                {
                    "field": key,
                    "code": "NOT_FOR_THIS_ROLE",
                    "message": f"A {role.value.replace('_', ' ')} cannot hold this permission",
                }
            ]
        )


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
        return effective(
            role,
            _org_type(role),
            admin_scopes=user.scope_list,
            role_overrides=await self.role_overrides(role),
            user_overrides=await self.user_overrides(user),
        )

    async def role_matrix(self) -> list[dict[str, Any]]:
        """For each editable role: every permission it may hold, whether it holds it, and whether that differs from the catalog."""
        out = []
        for role in EDITABLE_ROLES:
            overrides = await self.role_overrides(role)
            held = role_defaults(role, overrides)
            out.append(
                {
                    "role": role.value,
                    "permissions": [
                        {"key": p.key, "allowed": p.key in held, "changed": p.key in overrides}
                        for p in PERMISSIONS
                        if eligible(p, role, _org_type(role))
                    ],
                }
            )
        return out

    async def user_view(self, user: User) -> dict[str, Any]:
        """Every permission this person may hold: from their role, their own grant/removal, and the result."""
        role = Role(user.role)
        if role == Role.SUPER_ADMIN:
            return {
                "editable": False,
                "permissions": [
                    {"key": k, "from_role": True, "override": None, "allowed": True} for k in sorted(BY_KEY)
                ],
            }
        from_role = role_defaults(role, await self.role_overrides(role)) | (
            set(user.scope_list) if role == Role.ADMIN else set()
        )
        overrides = {} if role == Role.ADMIN else await self.user_overrides(user)
        result = set(await self.effective_for(user))
        return {
            "editable": True,
            "permissions": [
                {
                    "key": p.key,
                    "from_role": p.key in from_role,
                    "override": overrides.get(p.key),
                    "allowed": p.key in result,
                }
                for p in PERMISSIONS
                if eligible(p, role, _org_type(role))
            ],
        }

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
        catalog = {p.key for p in PERMISSIONS if role in p.default_roles}
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

        An admin's platform permissions are their scopes, so for an admin this edits the scopes themselves.
        """
        role = Role(target.role)
        if role == Role.SUPER_ADMIN:
            raise PermissionDeniedError("A super admin always holds every permission.")
        for key in changes:
            _check(key, role)
        if role == Role.ADMIN:
            scopes = set(target.scope_list)
            for key, allowed in changes.items():
                (scopes.add if allowed else scopes.discard)(key)
            target.set_scopes(sorted(scopes))
        else:
            defaults = role_defaults(role, await self.role_overrides(role))
            for key, allowed in changes.items():
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
