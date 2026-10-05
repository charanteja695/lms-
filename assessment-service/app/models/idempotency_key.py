from sqlalchemy import BigInteger, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class IdempotencyKey(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Remembers an ``Idempotency-Key`` so a retried create (a double click, a network retry) returns
    the run or submission it already made instead of making, and judging, a second one."""

    __tablename__ = "idempotency_keys"

    user_id: Mapped[int] = mapped_column(BigInteger)
    scope: Mapped[str] = mapped_column(String(20))
    key: Mapped[str] = mapped_column(String(80))
    request_hash: Mapped[str] = mapped_column(String(64))  # the same key with a different body is a client bug
    resource_public_id: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (
        UniqueConstraint("user_id", "scope", "key", name="uq_idempotency_keys_user_scope_key"),
        Index("ix_idempotency_keys_created", "created_at"),
    )
