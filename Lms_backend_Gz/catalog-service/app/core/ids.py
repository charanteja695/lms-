"""Public id generation and parsing (see lms-backend/README.md §"IDs").

Thin re-export: the implementation is shared across every service (lms_common.ids).
"""

from lms_common.ids import new_public_id, parse_public_id

EXAMPLE_COURSE_ID = "1755000000000123"
EXAMPLE_MODULE_ID = "1755000000000456"
EXAMPLE_TOPIC_ID = "1755000000000789"
EXAMPLE_TOPIC_ITEM_ID = "1755000000000987"
EXAMPLE_LEARNING_PATH_ID = "1755000000000654"

__all__ = [
    "EXAMPLE_COURSE_ID",
    "EXAMPLE_LEARNING_PATH_ID",
    "EXAMPLE_MODULE_ID",
    "EXAMPLE_TOPIC_ID",
    "EXAMPLE_TOPIC_ITEM_ID",
    "new_public_id",
    "parse_public_id",
]
