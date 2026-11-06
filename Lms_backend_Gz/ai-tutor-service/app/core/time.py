from datetime import UTC, datetime


def utcnow() -> datetime:
    """Timezone-aware current UTC time. Never use naive datetimes in this service."""
    return datetime.now(UTC)


def period_of(when: datetime) -> str:
    """The quota/usage period a timestamp falls in: a calendar month, ``"YYYY-MM"``."""
    return when.strftime("%Y-%m")
