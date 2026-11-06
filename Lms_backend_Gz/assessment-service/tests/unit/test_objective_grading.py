import pytest

from app.domain.enums import QuestionType as T
from app.grading.objective import grade_judged, grade_objective, grade_rubric, unanswered


def test_unanswered_earns_nothing_and_is_never_penalised():
    grade = grade_objective(T.MCQ_SINGLE, {"correct": "a"}, None, 4, negative_percent=50)
    assert grade == unanswered()
    assert grade.marks == 0 and grade.answered is False


def test_mcq_single_right_and_wrong():
    key = {"correct": "b"}
    assert grade_objective(T.MCQ_SINGLE, key, {"selected": "b"}, 2).marks == 2
    wrong = grade_objective(T.MCQ_SINGLE, key, {"selected": "a"}, 2)
    assert wrong.marks == 0 and wrong.is_correct is False


def test_negative_marking_punishes_a_wrong_guess_only():
    key = {"correct": "b"}
    assert grade_objective(T.MCQ_SINGLE, key, {"selected": "a"}, 4, negative_percent=25).marks == -1
    assert grade_objective(T.MCQ_SINGLE, key, {"selected": "b"}, 4, negative_percent=25).marks == 4


def test_negative_marking_does_not_apply_to_types_that_cannot_be_guessed():
    key = {"pairs": {"l1": "r1", "l2": "r2"}, "scoring": "partial"}
    grade = grade_objective(T.MATCH, key, {"pairs": {"l1": "r2", "l2": "r1"}}, 4, negative_percent=50)
    assert grade.marks == 0


def test_mcq_multi_all_or_nothing():
    key = {"correct": ["a", "c"], "scoring": "all_or_nothing"}
    assert grade_objective(T.MCQ_MULTI, key, {"selected": ["a", "c"]}, 3).marks == 3
    assert grade_objective(T.MCQ_MULTI, key, {"selected": ["a"]}, 3).marks == 0
    assert grade_objective(T.MCQ_MULTI, key, {"selected": ["a", "b", "c"]}, 3).marks == 0


def test_mcq_multi_partial_credit_subtracts_wrong_picks():
    key = {"correct": ["a", "c"], "scoring": "partial"}
    assert grade_objective(T.MCQ_MULTI, key, {"selected": ["a"]}, 4).marks == 2
    assert grade_objective(T.MCQ_MULTI, key, {"selected": ["a", "b"]}, 4).marks == 0  # 1 right - 1 wrong
    assert grade_objective(T.MCQ_MULTI, key, {"selected": ["b"]}, 4).marks == 0


def test_true_false():
    assert grade_objective(T.TRUE_FALSE, {"correct": True}, {"value": True}, 1).marks == 1
    assert grade_objective(T.TRUE_FALSE, {"correct": True}, {"value": False}, 1).marks == 0
    assert grade_objective(T.TRUE_FALSE, {"correct": False}, {"value": False}, 1).marks == 1


def test_fill_in_case_insensitive_by_default_and_partial():
    key = {
        "blanks": [
            {"answers": ["Paris"], "case_sensitive": False, "tolerance": None},
            {"answers": ["Rome", "roma"], "case_sensitive": True, "tolerance": None},
        ],
        "scoring": "partial",
    }
    assert grade_objective(T.FILL_IN, key, {"values": ["paris", "roma"]}, 4).marks == 4
    assert grade_objective(T.FILL_IN, key, {"values": ["paris", "ROMA"]}, 4).marks == 2
    assert grade_objective(T.FILL_IN, key, {"values": [None, None]}, 4).marks == 0


def test_fill_in_numeric_tolerance():
    key = {"blanks": [{"answers": ["3.14"], "case_sensitive": False, "tolerance": 0.01}], "scoring": "all_or_nothing"}
    assert grade_objective(T.FILL_IN, key, {"values": ["3.145"]}, 1).marks == 1
    assert grade_objective(T.FILL_IN, key, {"values": ["3.2"]}, 1).marks == 0
    assert grade_objective(T.FILL_IN, key, {"values": ["pi"]}, 1).marks == 0


def test_match_partial_and_all_or_nothing():
    pairs = {"l1": "r1", "l2": "r2", "l3": "r3", "l4": "r4"}
    answer = {"pairs": {"l1": "r1", "l2": "r2", "l3": "r4", "l4": "r3"}}
    assert grade_objective(T.MATCH, {"pairs": pairs, "scoring": "partial"}, answer, 8).marks == 4
    assert grade_objective(T.MATCH, {"pairs": pairs, "scoring": "all_or_nothing"}, answer, 8).marks == 0
    assert grade_objective(T.MATCH, {"pairs": pairs, "scoring": "all_or_nothing"}, {"pairs": pairs}, 8).marks == 8


def test_ordering_partial_counts_items_in_place():
    key = {"order": ["a", "b", "c", "d"], "scoring": "partial"}
    assert grade_objective(T.ORDERING, key, {"order": ["a", "b", "d", "c"]}, 4).marks == 2
    assert grade_objective(T.ORDERING, {**key, "scoring": "all_or_nothing"}, {"order": ["a", "b", "d", "c"]}, 4).marks == 0
    assert grade_objective(T.ORDERING, key, {"order": ["a", "b", "c", "d"]}, 4).marks == 4


def test_judged_uses_the_weighted_percentage():
    assert grade_judged({"scoring": "partial"}, 75, 8).marks == 6
    assert grade_judged({"scoring": "all_or_nothing"}, 99, 8).marks == 0
    assert grade_judged({"scoring": "all_or_nothing"}, 100, 8).marks == 8
    assert grade_judged({"scoring": "partial"}, None, 8).marks == 0


def test_rubric_grade_clamps_each_criterion_to_its_maximum():
    rubric = [{"id": "a", "criterion": "x", "max_marks": 4.0}, {"id": "b", "criterion": "y", "max_marks": 6.0}]
    assert grade_rubric(rubric, {"a": 4, "b": 3}, 10).marks == 7
    assert grade_rubric(rubric, {"a": 99, "b": 99}, 10).marks == 10
    assert grade_rubric(rubric, {}, 10).marks == 0


def test_grading_a_manual_type_here_is_a_bug():
    with pytest.raises(ValueError):
        grade_objective(T.SUBJECTIVE, {}, {"text": "x"}, 1)
