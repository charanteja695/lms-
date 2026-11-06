from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import DriveStatus, OfferStatus


class Offer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "offers"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    application_id: Mapped[Any] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"), unique=True)
    ctc: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    joining_date: Mapped[date | None] = mapped_column(Date)
    role_title: Mapped[str] = mapped_column(String(160))
    note: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(10), default=OfferStatus.EXTENDED)
    expires_at: Mapped[datetime]
    created_by: Mapped[int] = mapped_column(BigInteger)
    responded_at: Mapped[datetime | None]
    response_note: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (Index("ix_offers_status_expires", "status", "expires_at"),)


class PlacementDrive(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A campus drive: an institution's head invites an employer; once the employer accepts, its jobs can be attached and are then
    visible only to that institution's students, and to the institution's staff and head."""

    __tablename__ = "placement_drives"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    organization_id: Mapped[int] = mapped_column(BigInteger)  # the institution
    employer_org_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(1000))
    drive_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default=DriveStatus.PROPOSED)
    created_by: Mapped[int] = mapped_column(BigInteger)
    responded_by: Mapped[int | None] = mapped_column(BigInteger)
    responded_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_placement_drives_org", "organization_id", "status"), Index("ix_placement_drives_employer", "employer_org_id", "status"))
