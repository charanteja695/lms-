from datetime import UTC, date, datetime, time


def utcnow() -> datetime:
    """Timezone-aware current UTC time. Never use naive datetimes in this service."""
    return datetime.now(UTC)


def start_of_day(day: date) -> datetime:
    """Midnight UTC at the start of ``day``."""
    return datetime.combine(day, time.min, tzinfo=UTC)
