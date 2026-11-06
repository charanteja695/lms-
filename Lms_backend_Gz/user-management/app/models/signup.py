from datetime import datetime

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class SignupRequest(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A self sign-up waiting for its emailed code. The account is created only when the code is confirmed, so an
    unconfirmed email never holds a username or blocks a later sign-up. Only hashes of the code are stored."""

    __tablename__ = "signup_requests"

    email: Mapped[str] = mapped_column(String(254))  # lower-cased
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    password_hash: Mapped[str] = mapped_column(String(255))
    otp_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime]
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    consumed_at: Mapped[datetime | None]
    request_ip: Mapped[str | None] = mapped_column(String(45))

    __table_args__ = (Index("ix_signup_requests_email_consumed_at", "email", "consumed_at"),)
