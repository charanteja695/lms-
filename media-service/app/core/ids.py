"""Public id generation and parsing (see lms-backend/README.md §"IDs").

Thin re-export: the implementation is shared across every service (lms_common.ids).
"""

from lms_common.ids import new_public_id, parse_public_id

EXAMPLE_MEDIA_ASSET_ID = "1755000000001123"
EXAMPLE_PLAYBACK_TOKEN_ID = "1755000000001456"

__all__ = [
    "EXAMPLE_MEDIA_ASSET_ID",
    "EXAMPLE_PLAYBACK_TOKEN_ID",
    "new_public_id",
    "parse_public_id",
]
