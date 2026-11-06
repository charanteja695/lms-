from datetime import UTC, datetime, timedelta

from app.tutor import hints
from app.tutor.blocking import OpenAttempt, blocking_attempt
from app.tutor.context import SourceLine, build_user_message, clock, normalize_history

NOW = datetime(2026, 9, 24, 10, 0, tzinfo=UTC)


def test_the_hint_ladder_climbs_one_rung_at_a_time_and_only_the_top_allows_the_solution():
    levels = []
    current = 0
    for _ in range(5):
        decision = hints.next_level(current, max_level=4)
        levels.append((decision.level, decision.solution_allowed))
        current = decision.level
    assert levels == [(1, False), (2, False), (3, False), (4, True), (4, True)]
    assert hints.next_level(4, max_level=4).ladder_finished


def test_every_rung_has_a_description_for_the_prompt():
    assert all(hints.describe(level) for level in range(1, 5))


def test_practice_tests_do_not_block_the_tutor_but_graded_ones_do():
    practice = OpenAttempt(1, "practice", NOW + timedelta(hours=1))
    final = OpenAttempt(2, "final", NOW + timedelta(hours=1))
    assert blocking_attempt([practice], NOW, 300) is None
    assert blocking_attempt([practice, final], NOW, 300) == final


def test_an_attempt_long_past_its_deadline_no_longer_blocks_but_one_inside_the_grace_does():
    assert blocking_attempt([OpenAttempt(1, "final", NOW - timedelta(seconds=100))], NOW, 300) is not None
    assert blocking_attempt([OpenAttempt(1, "final", NOW - timedelta(seconds=301))], NOW, 300) is None


def test_an_attempt_with_no_deadline_blocks_until_it_is_submitted():
    assert blocking_attempt([OpenAttempt(1, "module", None)], NOW, 300) is not None


def test_the_user_message_labels_everything_that_is_data():
    text = build_user_message(
        "Why?", sources=[SourceLine(1, "Basics > Functions > Recursion", "A function calls itself.")], code="print(1)", language="python", facts="- Enrolment: active",
        faq=[("What is X?", "Y")],
    )
    assert text.index("SOURCES") < text.index("FAQ ENTRIES") < text.index("FACTS ABOUT THIS STUDENT") < text.index("STUDENT CODE (python)") < text.index("QUESTION:\nWhy?")
    assert "[1] Basics > Functions > Recursion" in text


def test_a_message_with_no_extras_is_just_the_question():
    assert build_user_message("Hi", sources=[], code=None, language=None, facts=None, faq=[]) == "QUESTION:\nHi"


def test_clock_formats_minutes_and_seconds():
    assert clock(760) == "12:40" and clock(5) == "0:05" and clock(None) == ""


def test_history_is_merged_into_alternating_turns_and_ends_with_the_new_question():
    turns = [("assistant", "stray"), ("user", "one"), ("user", "two"), ("assistant", "answer")]
    assert normalize_history(turns, "three", 1000) == [{"role": "user", "content": "one\n\ntwo"}, {"role": "assistant", "content": "answer"}, {"role": "user", "content": "three"}]


def test_history_keeps_the_newest_turns_that_fit():
    turns = [("user", "a" * 50), ("assistant", "b" * 50), ("user", "c" * 50), ("assistant", "d" * 50)]
    kept = normalize_history(turns, "q", 120)
    assert [(m["role"], m["content"][0]) for m in kept] == [("user", "c"), ("assistant", "d"), ("user", "q")]


def test_history_that_starts_with_an_assistant_turn_drops_it():
    assert normalize_history([("assistant", "hello")], "q", 100) == [{"role": "user", "content": "q"}]
