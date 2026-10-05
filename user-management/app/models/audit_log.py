import uuid
from typing import Any

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_public_id
from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType


class AuditLog(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Append-only security/audit trail. No foreign keys, so records outlive the rows they describe."""

    __tablename__ = "audit_logs"

    public_id: Mapped[int] = mapped_column(BigInteger, default=new_public_id)  # API audit_log_id
    actor_id: Mapped[uuid.UUID | None]
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[uuid.UUID | None]
    institution_id: Mapped[uuid.UUID | None]
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    request_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    __table_args__ = (
        Index("ix_audit_logs_actor_id_created_at", "actor_id", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_institution_id_created_at", "institution_id", "created_at"),
        Index("ix_audit_logs_action_created_at", "action", "created_at"),
        Index("ix_audit_logs_created_at", "created_at"),
        # A unique index rather than a constraint, so the migration also runs on SQLite (local development).
        Index("uq_audit_logs_public_id", "public_id", unique=True),
    )
