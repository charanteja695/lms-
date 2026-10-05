from datetime import datetime

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.domain.enums import InstitutionStatus


class InstitutionRef(TimestampMixin, Base):
    """Local read-model of an institution, kept in sync from user-management's
    ``institution.*`` outbox events (see app/events/consumers/institution_events.py).

    This service never reads user-management's tables directly (see lms-backend/README.md
    §1): a course request can only reference an institution already known here. The natural
    key (``organization_id``, the public id) is the primary key — this table is a pure cache,
    never itself exposed as a resource with its own id.
    """

    __tablename__ = "institution_refs"

    organization_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=InstitutionStatus.ACTIVE, server_default=InstitutionStatus.ACTIVE)
    deleted_at: Mapped[datetime | None]
