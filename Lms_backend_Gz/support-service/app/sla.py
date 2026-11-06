"""SLA arithmetic (docs/PRODUCT.md §5.5: "SLA timers"). Pure functions over times, so the rules are testable without a database.

A ticket has two clocks, started at its *anchor* (creation, or the last reopen): a first-response target and a resolution
target. Time spent **waiting on the student** does not count against either: while paused the due times do not move on the
calendar, and on resume the paused duration is added to the total that is folded into every due time. Wall-clock minutes only —
there is no business-hours calendar.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.config import DEFAULT_FIRST_RESPONSE_MINUTES, DEFAULT_RESOLUTION_MINUTES


@dataclass(frozen=True, slots=True)
class Targets:
    first_response_minutes: int
    resolution_minutes: int


def targets_for(queue: str, priority: str, overrides: dict[tuple[str, str], Targets]) -> Targets:
    override = overrides.get((queue, priority))
    if override is not None:
        return override
    return Targets(DEFAULT_FIRST_RESPONSE_MINUTES[priority], DEFAULT_RESOLUTION_MINUTES[priority])


def due_at(anchor: datetime, minutes: int, paused_seconds: int) -> datetime:
    return anchor + timedelta(minutes=minutes, seconds=paused_seconds)


def paused_total(paused_seconds: int, paused_at: datetime | None, now: datetime) -> int:
    """The total paused time after resuming at ``now`` (a pause that never started adds nothing)."""
    if paused_at is None:
        return paused_seconds
    return paused_seconds + max(int((now - paused_at).total_seconds()), 0)


def is_breached(now: datetime, due: datetime | None, *, paused: bool) -> bool:
    """A clock that is paused, or has no target, cannot breach."""
    return due is not None and not paused and now > due


def minutes_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return round((end - start).total_seconds() / 60, 1)
