"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class AssetKind(StrEnum):
    VIDEO = "video"
    IMAGE = "image"  # thumbnails, cover images


class AssetStatus(StrEnum):
    """upload requested -> object confirmed in S3 -> pipeline processing -> ready to play.

    uploading --complete--> uploaded --process--> processing --done--> ready
                                                                 '----> failed
    Any non-terminal or ready asset can move to archived (see docs/PRODUCT.md §3.3).
    """

    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    ARCHIVED = "archived"
