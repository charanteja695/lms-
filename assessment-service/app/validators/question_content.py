"""Checks a question's ``body`` (what the student sees) and ``answer_key`` (what is correct) at authoring time, so a
malformed question can never reach a paper. Returns the normalised pair; anything unknown is dropped, never stored.

Shapes per type (docs/PRODUCT.md §5.1; the full reference is in docs/API.md):

  mcq_single       body {options:[{id,text}]}                       key {correct:"id"}
  mcq_multi        body {options:[{id,text}]}                       key {correct:["id"], scoring:"all_or_nothing"|"partial"}
  true_false       body {}                                          key {correct:true|false}
  fill_in          body {blanks:n}                                  key {blanks:[{answers:[..], case_sensitive, tolerance}], scoring}
  match            body {left:[{id,text}], right:[{id,text}]}       key {pairs:{leftId:rightId}, scoring}
  ordering         body {items:[{id,text}]}                         key {order:["id"], scoring}
  coding | sql     body {problem_id, languages?}                    key {scoring:"partial"|"all_or_nothing"}
  subjective       body {rubric?:[{id,criterion,max_marks}], max_words?}   key {model_answer?}
  file_submission  body {allowed_extensions?, max_files?, max_size_mb?, rubric?}   key {}
"""

import re
from typing import Any

from app.core.config import Settings
from app.core.exceptions import ValidationFailedError
from app.core.ids import parse_public_id
from app.domain.enums import QuestionType

_ITEM_ID = re.compile(r"^[A-Za-z0-9_-]{1,20}$")
_EXTENSION = re.compile(r"^[a-z0-9]{1,10}$")
_LANGUAGE = re.compile(r"^[a-z0-9_+#-]{1,30}$")
MAX_ITEM_TEXT = 1_000
MAX_BLANKS = 10
MAX_ANSWERS_PER_BLANK = 20


class _Problems:
    def __init__(self) -> None:
        self.details: list[dict[str, Any]] = []

    def add(self, field: str, code: str, message: str) -> None:
        self.details.append({"field": field, "code": code, "message": message})

    def raise_if_any(self) -> None:
        if self.details:
            raise ValidationFailedError(details=self.details)


def _items(raw: Any, field: str, problems: _Problems, *, minimum: int, maximum: int) -> list[dict[str, str]]:
    """A list of {id, text} with unique ids."""
    if not isinstance(raw, list):
        problems.add(field, "INVALID_TYPE", "Must be a list")
        return []
    if not minimum <= len(raw) <= maximum:
        problems.add(field, "OUT_OF_RANGE", f"Needs between {minimum} and {maximum} entries")
        return []
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        where = f"{field}[{index}]"
        item_id = entry.get("id") if isinstance(entry, dict) else None
        text = entry.get("text") if isinstance(entry, dict) else None
        if not isinstance(item_id, str) or not _ITEM_ID.fullmatch(item_id):
            problems.add(where + ".id", "INVALID_ID", "Use 1-20 letters, digits, hyphens or underscores")
            continue
        if item_id in seen:
            problems.add(where + ".id", "DUPLICATE_ID", f"Id {item_id!r} is used more than once")
            continue
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_ITEM_TEXT:
            problems.add(where + ".text", "INVALID_TEXT", f"Must be 1-{MAX_ITEM_TEXT} characters")
            continue
        seen.add(item_id)
        items.append({"id": item_id, "text": text.strip()})
    return items


def _scoring(key: dict[str, Any], problems: _Problems, *, allowed: tuple[str, ...], default: str) -> str:
    value = key.get("scoring", default)
    if value not in allowed:
        problems.add("answer_key.scoring", "INVALID_OPTION", f"Must be one of: {', '.join(allowed)}")
        return default
    return str(value)


def _rubric(raw: Any, field: str, problems: _Problems) -> list[dict[str, Any]]:
    if raw in (None, []):
        return []
    if not isinstance(raw, list) or len(raw) > 20:
        problems.add(field, "INVALID_TYPE", "Must be a list of at most 20 criteria")
        return []
    rubric: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw):
        where = f"{field}[{index}]"
        criterion_id = entry.get("id") if isinstance(entry, dict) else None
        criterion = entry.get("criterion") if isinstance(entry, dict) else None
        max_marks = entry.get("max_marks") if isinstance(entry, dict) else None
        if not isinstance(criterion_id, str) or not _ITEM_ID.fullmatch(criterion_id) or criterion_id in seen:
            problems.add(where + ".id", "INVALID_ID", "Use a unique id of 1-20 letters, digits, hyphens or underscores")
            continue
        if not isinstance(criterion, str) or not criterion.strip() or len(criterion) > MAX_ITEM_TEXT:
            problems.add(where + ".criterion", "INVALID_TEXT", f"Must be 1-{MAX_ITEM_TEXT} characters")
            continue
        if isinstance(max_marks, bool) or not isinstance(max_marks, int | float) or not 0 < max_marks <= 1_000:
            problems.add(where + ".max_marks", "OUT_OF_RANGE", "Must be a number above 0 and up to 1000")
            continue
        seen.add(criterion_id)
        rubric.append({"id": criterion_id, "criterion": criterion.strip(), "max_marks": float(max_marks)})
    return rubric


def _mcq(qtype: QuestionType, body: dict[str, Any], key: dict[str, Any], settings: Settings, problems: _Problems) -> tuple[dict[str, Any], dict[str, Any]]:
    options = _items(body.get("options"), "body.options", problems, minimum=2, maximum=settings.MAX_OPTIONS_PER_QUESTION)
    ids = {option["id"] for option in options}
    correct = key.get("correct")
    if qtype == QuestionType.MCQ_SINGLE:
        if not isinstance(correct, str) or correct not in ids:
            problems.add("answer_key.correct", "INVALID_ANSWER_KEY", "Must be the id of exactly one option")
        return {"options": options}, {"correct": correct}
    if (
        not isinstance(correct, list)
        or not correct
        or len(set(correct)) != len(correct)
        or not all(isinstance(value, str) and value in ids for value in correct)
    ):
        problems.add("answer_key.correct", "INVALID_ANSWER_KEY", "Must list the ids of one or more distinct options")
        correct = []
    elif len(correct) == len(ids):
        problems.add("answer_key.correct", "INVALID_ANSWER_KEY", "At least one option must be wrong")
    scoring = _scoring(key, problems, allowed=("all_or_nothing", "partial"), default="all_or_nothing")
    return {"options": options}, {"correct": sorted(correct), "scoring": scoring}


def _fill_in(body: dict[str, Any], key: dict[str, Any], problems: _Problems) -> tuple[dict[str, Any], dict[str, Any]]:
    blanks = body.get("blanks")
    if isinstance(blanks, bool) or not isinstance(blanks, int) or not 1 <= blanks <= MAX_BLANKS:
        problems.add("body.blanks", "OUT_OF_RANGE", f"Must be a whole number from 1 to {MAX_BLANKS}")
        return {}, {}
    raw_blanks = key.get("blanks")
    if not isinstance(raw_blanks, list) or len(raw_blanks) != blanks:
        problems.add("answer_key.blanks", "INVALID_ANSWER_KEY", f"Needs one entry for each of the {blanks} blanks")
        return {"blanks": blanks}, {}
    accepted: list[dict[str, Any]] = []
    for index, entry in enumerate(raw_blanks):
        where = f"answer_key.blanks[{index}]"
        answers = entry.get("answers") if isinstance(entry, dict) else None
        if (
            not isinstance(answers, list)
            or not 1 <= len(answers) <= MAX_ANSWERS_PER_BLANK
            or not all(isinstance(answer, str) and answer.strip() and len(answer) <= 200 for answer in answers)
        ):
            problems.add(where + ".answers", "INVALID_ANSWER_KEY", "List 1-20 accepted answers of up to 200 characters")
            continue
        tolerance = entry.get("tolerance")
        if tolerance is not None:
            if isinstance(tolerance, bool) or not isinstance(tolerance, int | float) or tolerance < 0:
                problems.add(where + ".tolerance", "OUT_OF_RANGE", "Must be a number of 0 or more")
                continue
            try:
                [float(answer) for answer in answers]
            except ValueError:
                problems.add(where + ".answers", "INVALID_ANSWER_KEY", "A numeric blank needs numeric answers")
                continue
        accepted.append(
            {
                "answers": [answer.strip() for answer in answers],
                "case_sensitive": bool(entry.get("case_sensitive", False)),
                "tolerance": float(tolerance) if tolerance is not None else None,
            }
        )
    scoring = _scoring(key, problems, allowed=("all_or_nothing", "partial"), default="all_or_nothing")
    return {"blanks": blanks}, {"blanks": accepted, "scoring": scoring}


def _match(body: dict[str, Any], key: dict[str, Any], problems: _Problems) -> tuple[dict[str, Any], dict[str, Any]]:
    left = _items(body.get("left"), "body.left", problems, minimum=2, maximum=12)
    right = _items(body.get("right"), "body.right", problems, minimum=2, maximum=14)
    pairs = key.get("pairs")
    left_ids = {item["id"] for item in left}
    right_ids = {item["id"] for item in right}
    if not isinstance(pairs, dict) or set(pairs) != left_ids or not all(isinstance(v, str) and v in right_ids for v in pairs.values()):
        problems.add("answer_key.pairs", "INVALID_ANSWER_KEY", "Must map every left id to one right id")
        pairs = {}
    elif len(set(pairs.values())) != len(pairs):
        problems.add("answer_key.pairs", "INVALID_ANSWER_KEY", "Two left items cannot share one right item")
    scoring = _scoring(key, problems, allowed=("all_or_nothing", "partial"), default="partial")
    return {"left": left, "right": right}, {"pairs": dict(pairs), "scoring": scoring}


def _ordering(body: dict[str, Any], key: dict[str, Any], problems: _Problems) -> tuple[dict[str, Any], dict[str, Any]]:
    items = _items(body.get("items"), "body.items", problems, minimum=2, maximum=12)
    order = key.get("order")
    if not isinstance(order, list) or sorted(order, key=str) != sorted((item["id"] for item in items), key=str):
        problems.add("answer_key.order", "INVALID_ANSWER_KEY", "Must list every item id exactly once, in the correct order")
        order = []
    scoring = _scoring(key, problems, allowed=("all_or_nothing", "partial"), default="all_or_nothing")
    return {"items": items}, {"order": list(order), "scoring": scoring}


def _judged(body: dict[str, Any], key: dict[str, Any], problems: _Problems) -> tuple[dict[str, Any], dict[str, Any]]:
    problem_id = body.get("problem_id")
    if not isinstance(problem_id, str) or parse_public_id(problem_id) is None:
        problems.add("body.problem_id", "INVALID_ID", "Must be the code-execution-service problem id (a numeric string)")
    languages = body.get("languages")
    normalised: list[str] | None = None
    if languages is not None:
        if not isinstance(languages, list) or not languages or not all(isinstance(v, str) and _LANGUAGE.fullmatch(v) for v in languages):
            problems.add("body.languages", "INVALID_TYPE", "Must be a non-empty list of language codes")
        else:
            normalised = sorted(set(languages))
    scoring = _scoring(key, problems, allowed=("all_or_nothing", "partial"), default="partial")
    return {"problem_id": problem_id, "languages": normalised}, {"scoring": scoring}


def _subjective(body: dict[str, Any], key: dict[str, Any], problems: _Problems) -> tuple[dict[str, Any], dict[str, Any]]:
    max_words = body.get("max_words")
    if max_words is not None and (isinstance(max_words, bool) or not isinstance(max_words, int) or not 1 <= max_words <= 20_000):
        problems.add("body.max_words", "OUT_OF_RANGE", "Must be a whole number from 1 to 20000")
        max_words = None
    model_answer = key.get("model_answer")
    if model_answer is not None and (not isinstance(model_answer, str) or len(model_answer) > 10_000):
        problems.add("answer_key.model_answer", "TOO_LONG", "Must be text of at most 10000 characters")
        model_answer = None
    return {"rubric": _rubric(body.get("rubric"), "body.rubric", problems), "max_words": max_words}, {"model_answer": model_answer}


def _file_submission(body: dict[str, Any], settings: Settings, problems: _Problems) -> tuple[dict[str, Any], dict[str, Any]]:
    extensions = body.get("allowed_extensions")
    if extensions is not None:
        cleaned = [str(v).lower().lstrip(".") for v in extensions] if isinstance(extensions, list) else []
        if not cleaned or not all(_EXTENSION.fullmatch(v) for v in cleaned):
            problems.add("body.allowed_extensions", "INVALID_TYPE", "Must be a non-empty list such as [\"pdf\", \"zip\"]")
            cleaned = []
        extensions = sorted(set(cleaned)) or None
    max_files = body.get("max_files", 1)
    if isinstance(max_files, bool) or not isinstance(max_files, int) or not 1 <= max_files <= settings.MAX_FILES_PER_ANSWER:
        problems.add("body.max_files", "OUT_OF_RANGE", f"Must be a whole number from 1 to {settings.MAX_FILES_PER_ANSWER}")
        max_files = 1
    max_size = body.get("max_size_mb", settings.ANSWER_FILE_MAX_MB)
    if isinstance(max_size, bool) or not isinstance(max_size, int) or not 1 <= max_size <= settings.ANSWER_FILE_MAX_MB:
        problems.add("body.max_size_mb", "OUT_OF_RANGE", f"Must be a whole number from 1 to {settings.ANSWER_FILE_MAX_MB}")
        max_size = settings.ANSWER_FILE_MAX_MB
    body_out = {
        "allowed_extensions": extensions,
        "max_files": max_files,
        "max_size_mb": max_size,
        "rubric": _rubric(body.get("rubric"), "body.rubric", problems),
    }
    return body_out, {}


def validate_question_content(
    qtype: QuestionType, body: dict[str, Any], key: dict[str, Any], settings: Settings
) -> tuple[dict[str, Any], dict[str, Any]]:
    problems = _Problems()
    if qtype in (QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI):
        result = _mcq(qtype, body, key, settings, problems)
    elif qtype == QuestionType.TRUE_FALSE:
        if not isinstance(key.get("correct"), bool):
            problems.add("answer_key.correct", "INVALID_ANSWER_KEY", "Must be true or false")
        result = ({}, {"correct": key.get("correct")})
    elif qtype == QuestionType.FILL_IN:
        result = _fill_in(body, key, problems)
    elif qtype == QuestionType.MATCH:
        result = _match(body, key, problems)
    elif qtype == QuestionType.ORDERING:
        result = _ordering(body, key, problems)
    elif qtype in (QuestionType.CODING, QuestionType.SQL):
        result = _judged(body, key, problems)
    elif qtype == QuestionType.SUBJECTIVE:
        result = _subjective(body, key, problems)
    else:
        result = _file_submission(body, settings, problems)
    problems.raise_if_any()
    return result
