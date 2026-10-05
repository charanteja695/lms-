from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import AuthorRole, MessageKind, Priority, TicketStatus


class Ticket(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tickets"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)  # the requester's institution: who handles a batch-staff ticket
    requester_user_id: Mapped[int] = mapped_column(BigInteger)
    subject: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(12))
    queue: Mapped[str] = mapped_column(String(20))
    priority: Mapped[str] = mapped_column(String(8), default=Priority.NORMAL)
    status: Mapped[str] = mapped_column(String(20), default=TicketStatus.OPEN)
    source: Mapped[str] = mapped_column(String(12))
    source_ref: Mapped[str | None] = mapped_column(String(80))  # the tutor conversation, for a hand-off
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    assignee_user_id: Mapped[int | None] = mapped_column(BigInteger)
    assigned_at: Mapped[datetime | None]

    # SLA (docs/PRODUCT.md §5.5 "SLA timers"): due times are pushed out while the ticket waits on the student
    first_response_due_at: Mapped[datetime | None]
    resolution_due_at: Mapped[datetime | None]
    sla_paused_at: Mapped[datetime | None]
    sla_anchor_at: Mapped[datetime | None]  # when the clock started: creation, or the last reopen
    sla_paused_seconds: Mapped[int] = mapped_column(Integer, default=0)  # total time spent waiting on the student since the anchor
    first_response_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    first_response_at: Mapped[datetime | None]
    resolved_at: Mapped[datetime | None]
    closed_at: Mapped[datetime | None]
    reopened_count: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_at: Mapped[datetime | None]

    # CSAT (docs/PRODUCT.md §5.5: "a CSAT survey afterwards")
    csat_requested_at: Mapped[datetime | None]
    csat_rating: Mapped[int | None] = mapped_column(Integer)
    csat_comment: Mapped[str | None] = mapped_column(String(500))
    csat_submitted_at: Mapped[datetime | None]

    messages: Mapped[list["TicketMessage"]] = relationship(back_populates="ticket", order_by="TicketMessage.seq", lazy="raise")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_tickets_idempotency_key"),
        Index("ix_tickets_queue_status", "queue", "status", "created_at"),
        Index("ix_tickets_org_queue", "organization_id", "queue", "status"),
        Index("ix_tickets_requester", "requester_user_id", "created_at"),
        Index("ix_tickets_assignee", "assignee_user_id", "status"),
        Index("ix_tickets_sla_first", "status", "first_response_due_at"),
    )


class TicketMessage(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "ticket_messages"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    ticket_id: Mapped[Any] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    author_user_id: Mapped[int | None] = mapped_column(BigInteger)
    author_role: Mapped[str] = mapped_column(String(10), default=AuthorRole.REQUESTER)
    kind: Mapped[str] = mapped_column(String(10), default=MessageKind.PUBLIC)
    body: Mapped[str] = mapped_column(Text)
    canned_reply_id: Mapped[int | None] = mapped_column(BigInteger)

    ticket: Mapped[Ticket] = relationship(back_populates="messages", lazy="raise")

    __table_args__ = (UniqueConstraint("ticket_id", "seq", name="uq_ticket_messages_ticket_seq"),)


class TicketEvent(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """The audit trail of a ticket: who did what, and what the service did on its own (SLA breaches, auto-close)."""

    __tablename__ = "ticket_events"

    ticket_id: Mapped[Any] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(30))
    actor_user_id: Mapped[int | None] = mapped_column(BigInteger)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    __table_args__ = (Index("ix_ticket_events_ticket", "ticket_id", "created_at"),)
