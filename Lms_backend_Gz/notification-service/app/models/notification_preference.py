from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class NotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user's email choice for one category. No row means the default (email on).
    The in-app inbox is always written, so there is no in-app preference."""

    __tablename__ = "notification_preferences"

    user_id: Mapped[int] = mapped_column(BigInteger)
    category: Mapped[str] = mapped_column(String(30))
    email_enabled: Mapped[bool]

    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_notification_preferences_user_category"),)
