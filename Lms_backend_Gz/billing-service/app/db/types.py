import secrets
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

# JSONB on PostgreSQL, plain JSON elsewhere (tests run on SQLite).
JSONType = JSON().with_variant(JSONB(), "postgresql")
# A JSON column whose Python None is SQL NULL (not the JSON value null), so "IS NULL" finds unset values.
NullableJSONType = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


def uuid7() -> uuid.UUID:
    """Time-ordered UUID (RFC 9562 v7): unique like v4 but keeps B-tree indexes compact."""
    unix_ms = time.time_ns() // 1_000_000
    raw = bytearray(unix_ms.to_bytes(6, "big") + secrets.token_bytes(10))
    raw[6] = (raw[6] & 0x0F) | 0x70  # version 7
    raw[8] = (raw[8] & 0x3F) | 0x80  # RFC 4122 variant
    return uuid.UUID(bytes=bytes(raw))


class UTCDateTime(TypeDecorator[datetime]):
    """Stores timestamps in UTC and always returns timezone-aware datetimes."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not allowed; use app.core.time.utcnow()")
        value = value.astimezone(UTC)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
