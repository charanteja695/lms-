from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.domain.enums import UserStatus


class UserRef(TimestampMixin, Base):
    """Local recipient directory, kept in sync from user-management's ``user.*`` events
    (see app/events/consumers/user_events.py). This service never reads user-management's tables.

    Holds only what delivery needs: who the person is, which organisation and role they have
    (to find "the heads of institution X") and where to email them. The public user id is the
    primary key; this table is a pure cache and is never exposed as a resource.
    """

    __tablename__ = "user_refs"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)
    role: Mapped[str] = mapped_column(String(30))
    first_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.ACTIVE, server_default=UserStatus.ACTIVE)

    __table_args__ = (Index("ix_user_refs_organization_role", "organization_id", "role"),)
