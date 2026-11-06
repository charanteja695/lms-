import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.media_asset import MediaAsset


class Caption(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A subtitle track (WebVTT) for one language. Populated by AI transcription once that
    pipeline exists (see catalog-service's ``transcript.ready`` consumer)."""

    __tablename__ = "captions"

    media_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"))
    language_code: Mapped[str] = mapped_column(String(8))
    storage_key: Mapped[str] = mapped_column(String(500))
    auto_generated: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    media_asset: Mapped["MediaAsset"] = relationship(back_populates="captions", lazy="raise")

    __table_args__ = (UniqueConstraint("media_asset_id", "language_code", name="uq_captions_media_asset_id_language"),)
