import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import EnrollmentStatus

if TYPE_CHECKING:
    from app.models.batch import Batch


class Enrollment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One student in one batch. ``public_id`` doubles as the idempotency key
    (``reservation_key``) sent to subscription-service's seat reserve/release (see
    app/clients/subscription_client.py) — a retried enrol/withdraw call never double-counts.
    """

    __tablename__ = "enrollments"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    batch_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("batches.id", ondelete="CASCADE"))
    student_user_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default=EnrollmentStatus.ACTIVE, server_default=EnrollmentStatus.ACTIVE)
    enrolled_at: Mapped[datetime]
    withdrawn_at: Mapped[datetime | None]

    batch: Mapped["Batch"] = relationship(lazy="raise")

    @property
    def batch_public_id(self) -> int:
        return self.batch.public_id

    __table_args__ = (
        # A student may hold only one ACTIVE enrolment per batch at a time (a withdrawn one
        # doesn't block re-enrolling, hence the partial index).
        Index(
            "uq_enrollments_batch_id_student_one_active",
            "batch_id",
            "student_user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )
