"""The prompt registry (docs/PRODUCT.md §6, `ai-gateway` row: "prompt registry + versions").

A ``Prompt`` is a stable name a caller asks for (``"tutor.explain_concept"``); each ``PromptVersion`` under it is an
immutable, reviewed template plus the model parameters and tool allow-list a call with that version is bound to. A
completion always renders a specific version, never a live-edited template, so a call from a month ago replays the
same way and an eval run compares like with like.
"""

from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import Capability, PromptStatus


class Prompt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prompts"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    capability: Mapped[str] = mapped_column(String(20), default=Capability.CHAT)
    owner_service: Mapped[str] = mapped_column(String(60))  # which service this prompt belongs to, e.g. "ai-tutor-service"
    description: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[int] = mapped_column(BigInteger)

    versions: Mapped[list["PromptVersion"]] = relationship(back_populates="prompt", order_by="PromptVersion.version")


class PromptVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prompt_versions"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    prompt_id: Mapped[Any] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    # {{variable}} placeholders; see app/prompt/render.py. Rendered as the system prompt — the conversation
    # itself (the caller's `messages`) is supplied fresh on every call, never stored here.
    template: Mapped[str] = mapped_column(Text)
    variables: Mapped[list[str]] = mapped_column(JSONType, default=list)  # required placeholder names
    allowed_tools: Mapped[list[str]] = mapped_column(JSONType, default=list)  # empty = no tool calling
    model_params: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)  # temperature, max_tokens, ...
    status: Mapped[str] = mapped_column(String(20), default=PromptStatus.DRAFT)
    created_by: Mapped[int] = mapped_column(BigInteger)
    activated_by: Mapped[int | None] = mapped_column(BigInteger)
    retired_by: Mapped[int | None] = mapped_column(BigInteger)

    prompt: Mapped[Prompt] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("prompt_id", "version", name="uq_prompt_versions_prompt_version"),
        # At most one ACTIVE version per prompt: enforced in PromptService under a row lock, not by the
        # database (a partial unique index keyed on a non-unique string column needs care per dialect; the
        # service already serialises activation, so the extra index would only guard against a bug, not a
        # legitimate concurrent path — see app/services/prompt_service.py).
        Index("ix_prompt_versions_prompt_status", "prompt_id", "status"),
    )
