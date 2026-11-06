"""Public id generation and parsing (see lms-backend/README.md §"IDs").

Thin re-export: the implementation is shared across every service (lms_common.ids).
"""

from lms_common.ids import new_public_id, parse_public_id

EXAMPLE_BATCH_ID = "1755000000005111"
EXAMPLE_ENROLLMENT_ID = "1755000000005222"

__all__ = ["EXAMPLE_BATCH_ID", "EXAMPLE_ENROLLMENT_ID", "new_public_id", "parse_public_id"]
