"""Public id generation and parsing (see lms-backend/README.md §"IDs").

Thin re-export: the implementation is shared across every service (lms_common.ids).
"""

from lms_common.ids import new_public_id, parse_public_id

EXAMPLE_PLAN_ID = "1755000000003111"
EXAMPLE_COURSE_REQUEST_ID = "1755000000003222"
EXAMPLE_SUBSCRIPTION_ID = "1755000000003333"
EXAMPLE_ORGANIZATION_ID = "1755000000003444"
EXAMPLE_COURSE_ID = "1755000000003555"

__all__ = [
    "EXAMPLE_COURSE_ID",
    "EXAMPLE_COURSE_REQUEST_ID",
    "EXAMPLE_ORGANIZATION_ID",
    "EXAMPLE_PLAN_ID",
    "EXAMPLE_SUBSCRIPTION_ID",
    "new_public_id",
    "parse_public_id",
]
