from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import AssetStatus

if TYPE_CHECKING:
    from app.models.caption import Caption
    from app.models.rendition import Rendition
    from app.models.transcript import Transcript


class MediaAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One uploaded clip or image (see docs/PRODUCT.md §3.3).

    ``context_type``/``context_id`` is an optional caller-supplied tag (e.g. the catalog
    course-version a clip belongs to) used only to react to ``course.retired`` — this service
    does not otherwise know or care about catalog-service's data model.
    """

    __tablename__ = "media_assets"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(20))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default=AssetStatus.UPLOADING, server_default=AssetStatus.UPLOADING)
    duration_seconds: Mapped[int | None]
    failed_reason: Mapped[str | None] = mapped_column(String(500))
    context_type: Mapped[str | None] = mapped_column(String(50), index=True)
    context_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    created_by: Mapped[int] = mapped_column(BigInteger)
    archived_at: Mapped[datetime | None]

    renditions: Mapped[list["Rendition"]] = relationship(
        back_populates="media_asset", order_by="Rendition.created_at", lazy="raise"
    )
    captions: Mapped[list["Caption"]] = relationship(back_populates="media_asset", lazy="raise")
    transcript: Mapped["Transcript | None"] = relationship(back_populates="media_asset", lazy="raise", uselist=False)
