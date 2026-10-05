"""The server-side timer (docs/PRODUCT.md §5.1: "the server-side timer is the authority").

Pure functions over plain data, so the same rules run on the hot answer-save path (from Redis) and in the database
path, and are covered by unit tests without a database.

An attempt has one overall deadline. A per-section test also gives each section its own clock: sections run in
order, a section ends when its time is up or the student finishes it, and the next one starts at that moment. The
result is deterministic from what is stored, so it can be recomputed at any time and never depends on which request
happened to notice a timeout first.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app.domain.enums import TimeMode


@dataclass(slots=True)
class SectionClock:
    position: int
    section_id: int  # the section's public id
    limit_seconds: int
    started_at: datetime | None = None
    deadline_at: datetime | None = None
    finished_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "position": self.position,
            "section_id": self.section_id,
            "limit_seconds": self.limit_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SectionClock":
        def when(value: str | None) -> datetime | None:
            return datetime.fromisoformat(value) if value else None

        return cls(
            position=data["position"],
            section_id=data["section_id"],
            limit_seconds=data["limit_seconds"],
            started_at=when(data["started_at"]),
            deadline_at=when(data["deadline_at"]),
            finished_at=when(data["finished_at"]),
        )


def overall_deadline(
    *,
    time_mode: str,
    duration_minutes: int | None,
    section_limits_seconds: list[int],
    started_at: datetime,
    window_end: datetime | None,
) -> datetime:
    """When the attempt as a whole ends. A scheduled exam that enforces its end cuts a late starter off there."""
    if time_mode == TimeMode.PER_SECTION:
        seconds = sum(section_limits_seconds)
    else:
        seconds = (duration_minutes or 0) * 60
    deadline = started_at + timedelta(seconds=seconds)
    return min(deadline, window_end) if window_end is not None else deadline


def start_first_section(sections: list[SectionClock], started_at: datetime, deadline: datetime) -> None:
    if sections:
        _open(sections[0], started_at, deadline)


def _open(section: SectionClock, at: datetime, overall: datetime) -> None:
    section.started_at = at
    section.deadline_at = min(at + timedelta(seconds=section.limit_seconds), overall)


def current(sections: list[SectionClock]) -> SectionClock | None:
    return next((section for section in sections if section.finished_at is None), None)


def advance(sections: list[SectionClock], now: datetime, overall: datetime) -> bool:
    """Close every section whose time is up (each ending at its own deadline, the next starting there). Returns
    True if anything changed."""
    changed = False
    while (section := current(sections)) is not None and section.deadline_at is not None and section.deadline_at <= now:
        section.finished_at = section.deadline_at
        following = next((s for s in sections if s.position > section.position), None)
        if following is not None:
            _open(following, section.finished_at, overall)
        changed = True
    return changed


def finish_current(sections: list[SectionClock], now: datetime, overall: datetime) -> SectionClock | None:
    """The student finishes the section they are in; the next one starts now. Returns the section that finished."""
    section = current(sections)
    if section is None:
        return None
    section.finished_at = now
    following = next((s for s in sections if s.position > section.position), None)
    if following is not None:
        _open(following, now, overall)
    return section


def shift(sections: list[SectionClock], seconds: float) -> None:
    """Un-pausing gives back the time the clock was stopped."""
    delta = timedelta(seconds=seconds)
    for section in sections:
        if section.finished_at is None and section.deadline_at is not None:
            section.deadline_at += delta


def all_finished(sections: list[SectionClock]) -> bool:
    return bool(sections) and current(sections) is None
