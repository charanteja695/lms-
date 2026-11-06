"""S3 object key helpers for ticket attachments."""

import re

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(original_filename: str) -> str:
    name = _UNSAFE.sub("_", original_filename.strip())[-150:]
    return name or "file"


def upload_prefix(user_id: int) -> str:
    """Every upload lands under its uploader's prefix, so a message can only carry files its author uploaded."""
    return f"support/{user_id}/"
