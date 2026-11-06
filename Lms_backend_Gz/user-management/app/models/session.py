import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_public_id
from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class UserSession(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A login. Access tokens carry its id, so revoking the session invalidates them immediately."""

    __tablename__ = "user_sessions"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, default=new_public_id)  # API "session_id"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    last_used_at: Mapped[datetime]
    expires_at: Mapped[datetime]  # absolute lifetime; refresh cannot extend past this
    revoked_at: Mapped[datetime | None]
    revoked_reason: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (Index("ix_user_sessions_user_id_revoked_at", "user_id", "revoked_at"),)


class RefreshToken(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One-time refresh token. Presenting an already-used token revokes the whole session."""

    __tablename__ = "refresh_tokens"

    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_sessions.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_refresh_tokens_session_id", "session_id"),)
