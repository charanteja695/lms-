"""What a student sees of a question, and what they may see of it afterwards.

The student view is the question's authoring ``body`` with this student's option order applied, and never the
answer key. Because it keeps the authoring shape, the same dict validates the student's answers
(``app/validators/answers.py``), so the cached paper is all the hot answer-save path needs.
"""

from typing import Any

from app.domain.enums import QuestionType


def _ordered(items: list[dict[str, Any]], order: list[str] | None) -> list[dict[str, Any]]:
    if not order:
        return items
    by_id = {item["id"]: item for item in items}
    return [by_id[item_id] for item_id in order if item_id in by_id]


def render_body(qtype: str, body: dict[str, Any], option_order: list[str] | None) -> dict[str, Any]:
    if qtype in (QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI):
        return {"options": _ordered(body["options"], option_order)}
    if qtype == QuestionType.MATCH:
        return {"left": body["left"], "right": _ordered(body["right"], option_order)}
    if qtype == QuestionType.ORDERING:
        return {"items": _ordered(body["items"], option_order)}
    return dict(body)


def render_question(
    *,
    question_public_id: int,
    position: int,
    section_public_id: int,
    section_position: int,
    qtype: str,
    text: str,
    marks: float,
    body: dict[str, Any],
    option_order: list[str] | None,
) -> dict[str, Any]:
    return {
        "question_id": str(question_public_id),
        "position": position,
        "section_id": str(section_public_id),
        "section_position": section_position,
        "question_type": qtype,
        "text": text,
        "marks": marks,
        "body": render_body(qtype, body, option_order),
    }


def review_view(answer_key: dict[str, Any], explanation: str | None) -> dict[str, Any]:
    """The correct answer and explanation, shown only once results are released and the test allows review."""
    return {"answer_key": answer_key, "explanation": explanation}
