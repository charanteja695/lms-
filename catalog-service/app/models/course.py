from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.course_version import CourseVersion


class Course(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A course shell. All authorable content lives on its :class:`CourseVersion` rows.

    Several versions may be published at once (subscriptions choose their own upgrade
    policy, see docs/PRODUCT.md §3.2), so "the live version(s)" is a query over
    ``course_versions.status``, never a single pointer on this row.
    """

    __tablename__ = "courses"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    summary: Mapped[str] = mapped_column(String(500))
    thumbnail_media_id: Mapped[int | None] = mapped_column(BigInteger)
    created_by: Mapped[int] = mapped_column(BigInteger, doc="public user_id of the author")
    archived_at: Mapped[datetime | None]

    versions: Mapped[list["CourseVersion"]] = relationship(
        back_populates="course", order_by="CourseVersion.version_number", lazy="raise"
    )
