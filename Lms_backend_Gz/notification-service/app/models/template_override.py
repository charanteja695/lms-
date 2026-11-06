from sqlalchemy import BigInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TemplateOverride(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Platform-wide wording that replaces the built-in default for one notification type and
    channel (defaults live in app/domain/notification_types.py). Deleting the row resets it."""

    __tablename__ = "notification_templates"

    type_key: Mapped[str] = mapped_column(String(100))
    channel: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    updated_by: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (UniqueConstraint("type_key", "channel", name="uq_notification_templates_type_channel"),)
