"""Grades the answers that need no human and no code run (docs/PRODUCT.md §5.1). Pure functions: the answer,
the question's body and key and its marks in, a ``Grade`` out — nothing here touches the database, so every rule is
covered by a plain unit test.

``fraction`` is the share of the question's marks earned (0.0-1.0); an all-or-nothing question is only ever 0 or 1.
Negative marking then punishes an answered question that earned nothing, on question types that can be guessed.
"""

from dataclasses import dataclass
from typing import Any

from app.domain.enums import NEGATIVE_MARKING_TYPES, QuestionType

_ROUND = 4


@dataclass(frozen=True, slots=True)
class Grade:
    fraction: float  # share of the marks earned, 0.0-1.0
    is_correct: bool | None  # None when the question was left unanswered
    marks: float  # may be negative (negative marking)
    answered: bool


def round_marks(value: float) -> float:
    return round(value + 0.0, _ROUND)  # + 0.0 turns -0.0 into 0.0


def unanswered() -> Grade:
    return Grade(fraction=0.0, is_correct=None, marks=0.0, answered=False)


def _finish(qtype: QuestionType, fraction: float, marks: float, negative_percent: int) -> Grade:
    fraction = max(0.0, min(1.0, fraction))
    if fraction == 0.0 and negative_percent and qtype in NEGATIVE_MARKING_TYPES:
        return Grade(fraction=0.0, is_correct=False, marks=round_marks(-marks * negative_percent / 100), answered=True)
    return Grade(fraction=fraction, is_correct=fraction >= 1.0, marks=round_marks(marks * fraction), answered=True)


def _score_parts(correct_parts: int, total_parts: int, *, partial: bool) -> float:
    if total_parts == 0:
        return 0.0
    if not partial:
        return 1.0 if correct_parts == total_parts else 0.0
    return correct_parts / total_parts


def grade_objective(
    qtype: QuestionType,
    key: dict[str, Any],
    response: dict[str, Any] | None,
    marks: float,
    *,
    negative_percent: int = 0,
) -> Grade:
    """Grade one answer. ``response`` must already be normalised by ``normalize_answer``."""
    if response is None:
        return unanswered()
    match qtype:
        case QuestionType.MCQ_SINGLE:
            fraction = 1.0 if response["selected"] == key["correct"] else 0.0
        case QuestionType.MCQ_MULTI:
            fraction = _mcq_multi(key, response)
        case QuestionType.TRUE_FALSE:
            fraction = 1.0 if response["value"] is key["correct"] else 0.0
        case QuestionType.FILL_IN:
            fraction = _fill_in(key, response)
        case QuestionType.MATCH:
            pairs = key["pairs"]
            right = sum(1 for left_id, right_id in response["pairs"].items() if pairs.get(left_id) == right_id)
            fraction = _score_parts(right, len(pairs), partial=key.get("scoring") == "partial")
        case QuestionType.ORDERING:
            order = key["order"]
            in_place = sum(1 for expected, given in zip(order, response["order"], strict=True) if expected == given)
            fraction = _score_parts(in_place, len(order), partial=key.get("scoring") == "partial")
        case _:
            raise ValueError(f"{qtype} is not graded here")
    return _finish(qtype, fraction, marks, negative_percent)


def _mcq_multi(key: dict[str, Any], response: dict[str, Any]) -> float:
    correct, selected = set(key["correct"]), set(response["selected"])
    if key.get("scoring") == "partial":
        return max(0.0, (len(selected & correct) - len(selected - correct)) / len(correct))
    return 1.0 if selected == correct else 0.0


def _blank_matches(spec: dict[str, Any], value: str | None) -> bool:
    if value is None:
        return False
    tolerance = spec.get("tolerance")
    if tolerance is not None:
        try:
            given = float(value)
        except ValueError:
            return False
        return any(abs(given - float(answer)) <= tolerance for answer in spec["answers"])
    if spec.get("case_sensitive"):
        return value in spec["answers"]
    return value.casefold() in {answer.casefold() for answer in spec["answers"]}


def _fill_in(key: dict[str, Any], response: dict[str, Any]) -> float:
    blanks = key["blanks"]
    right = sum(1 for spec, value in zip(blanks, response["values"], strict=True) if _blank_matches(spec, value))
    return _score_parts(right, len(blanks), partial=key.get("scoring") == "partial")


def grade_judged(key: dict[str, Any], score_percent: int | None, marks: float) -> Grade:
    """A coding/SQL answer: code-execution-service reports 0-100 (weighted test cases). All-or-nothing questions
    only count a full pass."""
    percent = max(0, min(100, score_percent or 0))
    fraction = percent / 100
    if key.get("scoring") == "all_or_nothing":
        fraction = 1.0 if percent == 100 else 0.0
    return Grade(fraction=fraction, is_correct=fraction >= 1.0, marks=round_marks(marks * fraction), answered=True)


def grade_rubric(rubric: list[dict[str, Any]], scores: dict[str, float], marks: float) -> Grade:
    """A manual grade from per-criterion scores: the share of the rubric's total earned, scaled to the marks."""
    total = sum(criterion["max_marks"] for criterion in rubric)
    earned = sum(min(max(scores.get(criterion["id"], 0.0), 0.0), criterion["max_marks"]) for criterion in rubric)
    fraction = earned / total if total else 0.0
    return Grade(fraction=fraction, is_correct=fraction >= 1.0, marks=round_marks(marks * fraction), answered=True)
