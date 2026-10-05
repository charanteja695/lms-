"""Editable service configuration: SLA overrides, canned replies, and the read-model of people."""

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SlaPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Overrides the platform default for one queue and priority (see app/core/config.py::DEFAULT_*_MINUTES)."""

    __tablename__ = "sla_policies"

    queue: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(8))
    first_response_minutes: Mapped[int] = mapped_column(Integer)
    resolution_minutes: Mapped[int] = mapped_column(Integer)
    updated_by: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (UniqueConstraint("queue", "priority", name="uq_sla_policies_queue_priority"),)


class CannedReply(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A saved answer an agent can insert into a reply. ``{{student_first_name}}`` and ``{{ticket_subject}}`` are filled in."""

    __tablename__ = "canned_replies"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    scope: Mapped[str] = mapped_column(String(14))
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (Index("ix_canned_replies_scope", "scope", "organization_id", "active"),)


class UserRef(TimestampMixin, Base):
    """From user-management's ``user.*`` events: the names an agent sees, and the role/institution used to check that
    a ticket is only ever assigned to someone who may handle it. Kept after a user is deleted (a ticket must stay readable)."""

    __tablename__ = "user_refs"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    role: Mapped[str] = mapped_column(String(20), default="")
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
