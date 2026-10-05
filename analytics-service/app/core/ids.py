"""Public id generation and parsing (see lms-backend/README.md §"IDs").

Thin re-export: the implementation is shared across every service (lms_common.ids).
"""

from lms_common.ids import new_public_id, parse_public_id

EXAMPLE_REPORT_ID = "1755000000100001"

__all__ = ["EXAMPLE_REPORT_ID", "new_public_id", "parse_public_id"]
