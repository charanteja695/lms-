from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType


class Profile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One per student: what a person says about themselves that is not a list item. Name and email are not here — they come
    from user-management (``user_refs``) and are shown as verified."""

    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    headline: Mapped[str | None] = mapped_column(String(160))
    summary: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(30))
    location: Mapped[str | None] = mapped_column(String(120))
    links: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)  # [{"label", "url"}]
    target_roles: Mapped[list[str]] = mapped_column(JSONType, default=list)
    revision: Mapped[int] = mapped_column(Integer, default=0)  # bumped on every change; carried by skill_profile.updated


class ProfileItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One entry of a profile. ``verified`` items are created by this service from platform events and cannot be edited or
    deleted by the student; ``self`` items are labelled as self-declared wherever they appear (docs/PRODUCT.md §5.6:
    "the AI never invents credentials. Verified items can't be edited, and self-declared items are labelled")."""

    __tablename__ = "profile_items"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(14))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(24))
    source_ref: Mapped[str | None] = mapped_column(String(40))  # certificate id / course id: makes event handling idempotent
    data: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)  # false once a certificate is revoked / a score invalidated
    inactive_reason: Mapped[str | None] = mapped_column(String(200))
    inactive_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("user_id", "kind", "source_ref", name="uq_profile_items_source"),
        Index("ix_profile_items_user_kind", "user_id", "kind", "position"),
    )
