"""S3 object key helpers for students' file answers."""

import re

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(original_filename: str) -> str:
    name = _UNSAFE.sub("_", original_filename.strip())[-150:]
    return name or "file"
