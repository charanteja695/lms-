import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin


class UserMfa(TimestampMixin, Base):
    """TOTP enrolment. Secrets are encrypted at rest (Fernet); nothing here is ever returned by the API."""

    __tablename__ = "user_mfa"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    secret_encrypted: Mapped[str | None] = mapped_column(String(255))
    pending_secret_encrypted: Mapped[str | None] = mapped_column(String(255))  # set-up started, not confirmed
    enabled_at: Mapped[datetime | None]
    # Highest TOTP time step accepted; a code can never be used twice.
    last_used_step: Mapped[int | None] = mapped_column(BigInteger)

    @property
    def is_enabled(self) -> bool:
        return self.enabled_at is not None and self.secret_encrypted is not None


class MfaRecoveryCode(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "mfa_recovery_codes"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    used_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_mfa_recovery_codes_user_id", "user_id"),)


class MfaChallenge(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Second login step: issued after a correct password, exchanged for tokens with a valid code."""

    __tablename__ = "mfa_challenges"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    expires_at: Mapped[datetime]
    consumed_at: Mapped[datetime | None]
    ip_address: Mapped[str | None] = mapped_column(String(45))

    __table_args__ = (Index("ix_mfa_challenges_user_id", "user_id"),)
