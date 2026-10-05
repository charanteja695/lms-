import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class PasswordResetPurpose(StrEnum):
    PASSWORD_RESET = "password_reset"  # forgot-password: OTP + link
    ACCOUNT_SETUP = "account_setup"  # new user without a password: link only


class PasswordResetRequest(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Only HMAC hashes of the OTP and tokens are stored; raw values exist only in the email."""

    __tablename__ = "password_reset_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(32))
    otp_hash: Mapped[str | None] = mapped_column(String(64))
    link_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]  # OTP and link expiry
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    verified_at: Mapped[datetime | None]
    # Issued after a correct OTP; exchanged for the new password.
    reset_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    reset_token_expires_at: Mapped[datetime | None]
    consumed_at: Mapped[datetime | None]
    request_ip: Mapped[str | None] = mapped_column(String(45))

    __table_args__ = (Index("ix_password_reset_requests_user_id_consumed_at", "user_id", "consumed_at"),)
