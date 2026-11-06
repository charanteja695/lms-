import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.enrollment import Enrollment


class ItemProgress(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One completed topic item for one enrolment. Marking the same item complete twice is a
    no-op (see app/services/progress_service.py) — the unique constraint is the safety net."""

    __tablename__ = "item_progress"

    enrollment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrollments.id", ondelete="CASCADE"))
    topic_item_id: Mapped[int] = mapped_column(ForeignKey("topic_item_refs.topic_item_id", ondelete="RESTRICT"))
    completed_at: Mapped[datetime]

    enrollment: Mapped["Enrollment"] = relationship(lazy="raise")

    __table_args__ = (UniqueConstraint("enrollment_id", "topic_item_id", name="uq_item_progress_enrollment_id_item_id"),)
