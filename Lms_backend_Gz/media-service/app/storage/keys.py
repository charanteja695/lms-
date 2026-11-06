"""S3 object key layout. Centralised so the pipeline and cleanup code agree on where things live."""

import re

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(original_filename: str) -> str:
    name = _UNSAFE.sub("_", original_filename.strip())[-150:]
    return name or "file"


def original_object_key(asset_public_id: int, original_filename: str) -> str:
    return f"assets/{asset_public_id}/original/{safe_filename(original_filename)}"


def rendition_object_key(asset_public_id: int, label: str) -> str:
    return f"assets/{asset_public_id}/renditions/{label}.mp4"
