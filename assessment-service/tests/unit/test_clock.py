from datetime import UTC, datetime, timedelta

from app.domain.enums import TimeMode
from app.services import clock
from app.services.clock import SectionClock

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def minutes(n: float) -> timedelta:
    return timedelta(minutes=n)


def sections(*limits: int) -> list[SectionClock]:
    return [SectionClock(position=i + 1, section_id=1000 + i, limit_seconds=limit * 60) for i, limit in enumerate(limits)]


def test_overall_deadline_is_the_duration_after_start():
    deadline = clock.overall_deadline(
        time_mode=TimeMode.OVERALL, duration_minutes=90, section_limits_seconds=[], started_at=T0, window_end=None
    )
    assert deadline == T0 + minutes(90)


def test_per_section_deadline_is_the_sum_of_the_section_limits():
    deadline = clock.overall_deadline(
        time_mode=TimeMode.PER_SECTION, duration_minutes=None, section_limits_seconds=[600, 1200], started_at=T0, window_end=None
    )
    assert deadline == T0 + minutes(30)


def test_a_late_starter_is_cut_off_at_the_window_end():
    window_end = T0 + minutes(20)
    deadline = clock.overall_deadline(
        time_mode=TimeMode.OVERALL, duration_minutes=60, section_limits_seconds=[], started_at=T0 + minutes(5), window_end=window_end
    )
    assert deadline == window_end


def test_first_section_starts_with_the_attempt_and_is_capped_by_the_overall_deadline():
    parts = sections(10, 20)
    clock.start_first_section(parts, T0, T0 + minutes(5))
    assert parts[0].started_at == T0 and parts[0].deadline_at == T0 + minutes(5)
    assert parts[1].started_at is None


def test_advance_closes_a_section_when_its_time_is_up_and_starts_the_next_at_that_moment():
    parts = sections(10, 20)
    overall = T0 + minutes(30)
    clock.start_first_section(parts, T0, overall)
    assert clock.advance(parts, T0 + minutes(9), overall) is False
    assert clock.advance(parts, T0 + minutes(12), overall) is True
    assert parts[0].finished_at == T0 + minutes(10)
    assert parts[1].started_at == T0 + minutes(10) and parts[1].deadline_at == T0 + minutes(30)
    assert clock.current(parts) is parts[1]


def test_advance_catches_up_over_several_sections_when_the_student_was_away():
    parts = sections(5, 5, 5)
    overall = T0 + minutes(15)
    clock.start_first_section(parts, T0, overall)
    clock.advance(parts, T0 + minutes(40), overall)
    assert clock.all_finished(parts)
    assert [s.finished_at for s in parts] == [T0 + minutes(5), T0 + minutes(10), T0 + minutes(15)]


def test_finishing_early_starts_the_next_section_now():
    parts = sections(10, 10)
    overall = T0 + minutes(20)
    clock.start_first_section(parts, T0, overall)
    finished = clock.finish_current(parts, T0 + minutes(3), overall)
    assert finished is parts[0] and parts[0].finished_at == T0 + minutes(3)
    assert parts[1].started_at == T0 + minutes(3) and parts[1].deadline_at == T0 + minutes(13)


def test_shift_gives_back_paused_time_to_the_open_section_only():
    parts = sections(10, 10)
    overall = T0 + minutes(20)
    clock.start_first_section(parts, T0, overall)
    clock.advance(parts, T0 + minutes(11), overall)
    clock.shift(parts, 120)
    assert parts[0].deadline_at == T0 + minutes(10)  # already closed: untouched
    assert parts[1].deadline_at == T0 + minutes(20) + timedelta(seconds=120)


def test_round_trip_through_a_dict_for_the_cache():
    parts = sections(10)
    clock.start_first_section(parts, T0, T0 + minutes(10))
    assert SectionClock.from_dict(parts[0].to_dict()) == parts[0]
