from datetime import datetime

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import EmployerStatus


class EmployerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A hiring company's public profile. One per employer organisation. Its jobs go live only while ``status`` is ``verified``
    (docs/PRODUCT.md §5.7: "verified by a platform admin before its jobs go live")."""

    __tablename__ = "employer_profiles"

    organization_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    about: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(300))
    industry: Mapped[str | None] = mapped_column(String(100))
    company_size: Mapped[str | None] = mapped_column(String(20))
    headquarters: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(10), default=EmployerStatus.DRAFT)
    submitted_at: Mapped[datetime | None]
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None]
    review_note: Mapped[str | None] = mapped_column(String(500))
    suspension_source: Mapped[str | None] = mapped_column(String(10))  # admin | account: an account suspension in user-management lifts itself; an admin's does not
    revision: Mapped[int] = mapped_column(Integer, default=0)
