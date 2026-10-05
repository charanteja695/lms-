"""Public identifiers exposed by every service's API (``user_id``, ``organization_id``, ``course_id``, ...).

Like Zoho record ids, they are 64-bit numbers transported as strings. Each id is 41 bits of
milliseconds since 2024-01-01 (valid until ~2093) followed by 22 random bits: time-ordered,
unguessable, and unrelated to internal database primary keys, which are never exposed.

Every service generates its own ids with :func:`new_public_id` (there is no central allocator).

Within one process ids are **strictly increasing and never repeat**: the random part is drawn as before, but if it
would not be greater than the last id issued (two ids in the same millisecond, or a clock that stepped back), the
last id plus one is issued instead. A burst of ids in one millisecond therefore cannot collide with itself (a bulk import,
a fan-out of events), and creation order is id order. Across processes and services there is still no coordination: two
processes that draw the same 22 random bits in the same millisecond would clash, which is astronomically unlikely and
harmless in practice because ids are always scoped to one resource type and enforced unique by the database.
"""

import re
import secrets
import threading
import time

_EPOCH_MS = 1_704_067_200_000  # 2024-01-01T00:00:00Z
_RANDOM_BITS = 22
_MAX_BIGINT = 2**63 - 1
_PUBLIC_ID_PATTERN = re.compile(r"^[1-9][0-9]{9,18}$")

_lock = threading.Lock()
_last = 0


def new_public_id() -> int:
    global _last
    elapsed_ms = int(time.time() * 1000) - _EPOCH_MS
    candidate = (elapsed_ms << _RANDOM_BITS) | secrets.randbits(_RANDOM_BITS)
    with _lock:
        if candidate <= _last:
            candidate = _last + 1
        _last = candidate
    return candidate


def parse_public_id(value: object) -> int | None:
    """Return the numeric id for a well-formed id string, otherwise ``None``."""
    if not isinstance(value, str) or not _PUBLIC_ID_PATTERN.fullmatch(value):
        return None
    number = int(value)
    return number if number <= _MAX_BIGINT else None
