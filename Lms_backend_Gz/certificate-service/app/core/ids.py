"""Public id generation and parsing (see lms-backend/README.md §"IDs").

Thin re-export: the implementation is shared across every service (lms_common.ids).
"""

from lms_common.ids import new_public_id, parse_public_id

__all__ = ["new_public_id", "parse_public_id"]
