"""Public identifiers exposed by the API (``user_id``, ``organization_id``, ``session_id``).

The generation and parsing logic is shared with every LMS service; see
``lms_common.ids`` for the format (a Zoho-style 64-bit id: time-ordered, unguessable, unrelated
to internal database primary keys). Re-exported here, plus this service's own example values
used in the API docs, so call sites keep importing from ``app.core.ids``.
"""

from lms_common.ids import _EPOCH_MS, _RANDOM_BITS, new_public_id, parse_public_id

EXAMPLE_USER_ID = "358672738860850316"
EXAMPLE_ORGANIZATION_ID = "358672738414054064"
EXAMPLE_SESSION_ID = "358672738835009029"

__all__ = [
    "EXAMPLE_ORGANIZATION_ID",
    "EXAMPLE_SESSION_ID",
    "EXAMPLE_USER_ID",
    "new_public_id",
    "parse_public_id",
]

_ = (_EPOCH_MS, _RANDOM_BITS)  # re-exported for the 0002 migration; not part of the public API
