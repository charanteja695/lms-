from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import ConversationStatus, EscalationStatus, MessageKind


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversations"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    mode: Mapped[str] = mapped_column(String(12))
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    version_id: Mapped[int | None] = mapped_column(BigInteger)  # the version the student is enrolled in when it began
    title: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(12), default=ConversationStatus.OPEN)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    low_confidence_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", order_by="Message.seq", lazy="raise")

    __table_args__ = (Index("ix_conversations_user", "user_id", "deleted_at", "last_message_at"),)


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    conversation_id: Mapped[Any] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(12))
    kind: Mapped[str] = mapped_column(String(16), default=MessageKind.QUESTION)
    content: Mapped[str] = mapped_column(Text)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONType)  # what the student had open, as they sent it
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONType)
    confidence: Mapped[float | None] = mapped_column(Float)
    retrieval: Mapped[str | None] = mapped_column(String(10))
    gateway_call_id: Mapped[int | None] = mapped_column(BigInteger)
    prompt_key: Mapped[str | None] = mapped_column(String(80))
    guardrail_flags: Mapped[list[str] | None] = mapped_column(JSONType)
    hint_level: Mapped[int | None] = mapped_column(Integer)
    idempotency_key: Mapped[str | None] = mapped_column(String(80))  # the client's Idempotency-Key, on the student's message

    conversation: Mapped[Conversation] = relationship(back_populates="messages", lazy="raise")

    __table_args__ = (
        UniqueConstraint("conversation_id", "seq", name="uq_messages_conversation_seq"),
        UniqueConstraint("conversation_id", "idempotency_key", name="uq_messages_conversation_idem"),
    )


class Feedback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A student's thumbs up/down on one assistant message (docs/PRODUCT.md §5.5 "Quality")."""

    __tablename__ = "feedback"

    message_id: Mapped[Any] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger)
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    rating: Mapped[str] = mapped_column(String(4))
    comment: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("message_id", "user_id", name="uq_feedback_message_user"), Index("ix_feedback_course", "course_id", "rating"))


class HintProgress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """How far up the hint ladder a student is on one practice item. Server-side and monotonic: the model is told the
    level, never asked to decide it, so "just give me the answer" cannot skip the ladder."""

    __tablename__ = "hint_progress"

    user_id: Mapped[int] = mapped_column(BigInteger)
    item_id: Mapped[int] = mapped_column(BigInteger)
    level: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_hint_progress_user_item"),)


class Escalation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The tutor handing a student to a person. Durable: the row is the job that creates the support ticket."""

    __tablename__ = "escalations"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    conversation_id: Mapped[Any] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    conversation_public_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    course_id: Mapped[int | None] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(12))
    subject: Mapped[str] = mapped_column(String(200), default="")
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default=EscalationStatus.PENDING)
    ticket_id: Mapped[int | None] = mapped_column(BigInteger)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None]
    lease_until: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (
        Index("ix_escalations_due", "status", "next_attempt_at"),
        Index("ix_escalations_conversation", "conversation_id"),
    )
