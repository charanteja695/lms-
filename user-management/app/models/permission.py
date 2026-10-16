"""Who holds which permission beyond the catalog's defaults (app/permissions/features.py).

Only differences are stored: a row says "this role (or this person) is allowed = true/false" for one permission.
No row → the catalog default (for a role) or the role's setting (for a person). Removing a row restores the default.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RolePermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A super admin's change to a role's default for one permission."""

    __tablename__ = "role_permissions"

    role: Mapped[str] = mapped_column(String(32))
    permission: Mapped[str] = mapped_column(String(64))
    allowed: Mapped[bool] = mapped_column(Boolean)
    changed_by: Mapped[uuid.UUID | None]

    __table_args__ = (Index("uq_role_permissions_role_permission", "role", "permission", unique=True),)


class UserPermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One person's grant (allowed) or removal (not allowed) of one permission, on top of their role."""

    __tablename__ = "user_permissions"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    permission: Mapped[str] = mapped_column(String(64))
    allowed: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str | None] = mapped_column(String(300))
    changed_by: Mapped[uuid.UUID | None]

    __table_args__ = (Index("uq_user_permissions_user_id_permission", "user_id", "permission", unique=True),)
