import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.media_asset import MediaAsset


class Transcript(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """The full text transcript of a video asset, indexed elsewhere for the AI tutor
    (see docs/PRODUCT.md §7). One per asset; populated by AI transcription once that exists."""

    __tablename__ = "transcripts"

    media_asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"), unique=True)
    language_code: Mapped[str] = mapped_column(String(8))
    storage_key: Mapped[str] = mapped_column(String(500))

    media_asset: Mapped["MediaAsset"] = relationship(back_populates="transcript", lazy="raise")
