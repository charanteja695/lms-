import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.media_asset import MediaAsset


class Rendition(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """A playable variant of a video asset. v1 has no real transcoder, so every asset gets
    exactly one rendition labelled ``source`` pointing at the original upload; the label set
    is designed to grow to ``240p``/``480p``/``720p``/``1080p`` once a transcoder exists."""

    __tablename__ = "renditions"

    media_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(20))
    storage_key: Mapped[str] = mapped_column(String(500))
    byte_size: Mapped[int | None] = mapped_column(BigInteger)

    media_asset: Mapped["MediaAsset"] = relationship(back_populates="renditions", lazy="raise")

    __table_args__ = (UniqueConstraint("media_asset_id", "label", name="uq_renditions_media_asset_id_label"),)
