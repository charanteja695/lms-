from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import BatchStatus

if TYPE_CHECKING:
    from app.models.course_version_ref import CourseVersionRef
    from app.models.institution_ref import InstitutionRef


class Batch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A group of one institution's students taking one published course version together
    (see docs/PRODUCT.md §4 "Create batch, enrol"). ``subscription_id`` is read once from the
    entitlement cache at creation time (see app/services/batch_service.py) and reused for every
    enrolment's seat reserve/release call — it never changes for the life of the batch.
    """

    __tablename__ = "batches"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("institution_refs.organization_id", ondelete="RESTRICT"))
    version_id: Mapped[int] = mapped_column(ForeignKey("course_version_refs.version_id", ondelete="RESTRICT"))
    subscription_id: Mapped[int] = mapped_column(BigInteger, doc="public id of the subscription-service subscription")
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default=BatchStatus.ACTIVE, server_default=BatchStatus.ACTIVE)
    created_by: Mapped[int] = mapped_column(BigInteger)

    institution: Mapped["InstitutionRef"] = relationship(lazy="raise")
    course_version: Mapped["CourseVersionRef"] = relationship(lazy="raise")

    __table_args__ = (Index("ix_batches_organization_id_status", "organization_id", "status"),)

    @property
    def course_id(self) -> int:
        """For display only (BatchOut); requires `course_version` to already be loaded."""
        return self.course_version.course_id

    @property
    def title(self) -> str:
        """The course's title, for display only (BatchOut); requires `course_version` loaded."""
        return self.course_version.title
