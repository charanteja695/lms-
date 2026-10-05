import pytest

from app.core.config import Settings
from app.core.exceptions import ValidationFailedError
from app.domain.enums import QuestionType as T
from app.validators.answers import normalize_answer
from app.validators.question_content import validate_question_content

SETTINGS = Settings(ENVIRONMENT="test")
OPTIONS = [{"id": "a", "text": "One"}, {"id": "b", "text": "Two"}, {"id": "c", "text": "Three"}]
MCQ_BODY = {"options": OPTIONS}


def validate(qtype, body, key):
    return validate_question_content(qtype, body, key, SETTINGS)


def fields(exc: ValidationFailedError) -> set[str]:
    return {detail["field"] for detail in exc.details}


def answer(qtype, body, response, **kw):
    return normalize_answer(qtype, body, response, max_bytes=70_000, **kw)


def test_mcq_single_normalises_and_checks_the_key():
    body, key = validate(T.MCQ_SINGLE, {"options": OPTIONS, "ignored": 1}, {"correct": "b"})
    assert body == {"options": OPTIONS} and key == {"correct": "b"}
    with pytest.raises(ValidationFailedError) as caught:
        validate(T.MCQ_SINGLE, {"options": OPTIONS}, {"correct": "z"})
    assert fields(caught.value) == {"answer_key.correct"}


def test_mcq_needs_two_unique_options():
    with pytest.raises(ValidationFailedError) as caught:
        validate(T.MCQ_SINGLE, {"options": [{"id": "a", "text": "x"}]}, {"correct": "a"})
    assert "body.options" in fields(caught.value)
    with pytest.raises(ValidationFailedError) as caught:
        validate(T.MCQ_SINGLE, {"options": [{"id": "a", "text": "x"}, {"id": "a", "text": "y"}]}, {"correct": "a"})
    assert any(d["code"] == "DUPLICATE_ID" for d in caught.value.details)


def test_mcq_multi_rejects_a_key_that_selects_everything():
    with pytest.raises(ValidationFailedError):
        validate(T.MCQ_MULTI, {"options": OPTIONS}, {"correct": ["a", "b", "c"]})
    _, key = validate(T.MCQ_MULTI, {"options": OPTIONS}, {"correct": ["c", "a"], "scoring": "partial"})
    assert key == {"correct": ["a", "c"], "scoring": "partial"}


def test_true_false_key_must_be_boolean():
    assert validate(T.TRUE_FALSE, {}, {"correct": False}) == ({}, {"correct": False})
    with pytest.raises(ValidationFailedError):
        validate(T.TRUE_FALSE, {}, {"correct": "yes"})


def test_fill_in_needs_one_key_entry_per_blank_and_numeric_answers_for_a_tolerance():
    good = {"blanks": [{"answers": ["7"], "tolerance": 0.5}]}
    body, key = validate(T.FILL_IN, {"blanks": 1}, good)
    assert body == {"blanks": 1} and key["blanks"][0]["tolerance"] == 0.5
    with pytest.raises(ValidationFailedError):
        validate(T.FILL_IN, {"blanks": 2}, good)
    with pytest.raises(ValidationFailedError):
        validate(T.FILL_IN, {"blanks": 1}, {"blanks": [{"answers": ["seven"], "tolerance": 0.5}]})


def test_match_key_must_map_every_left_item_to_a_distinct_right_item():
    left = [{"id": "l1", "text": "a"}, {"id": "l2", "text": "b"}]
    right = [{"id": "r1", "text": "x"}, {"id": "r2", "text": "y"}, {"id": "r3", "text": "decoy"}]
    _, key = validate(T.MATCH, {"left": left, "right": right}, {"pairs": {"l1": "r2", "l2": "r1"}})
    assert key["scoring"] == "partial"
    with pytest.raises(ValidationFailedError):
        validate(T.MATCH, {"left": left, "right": right}, {"pairs": {"l1": "r1", "l2": "r1"}})
    with pytest.raises(ValidationFailedError):
        validate(T.MATCH, {"left": left, "right": right}, {"pairs": {"l1": "r1"}})


def test_ordering_key_must_be_a_permutation_of_the_items():
    items = [{"id": "a", "text": "1"}, {"id": "b", "text": "2"}, {"id": "c", "text": "3"}]
    _, key = validate(T.ORDERING, {"items": items}, {"order": ["c", "a", "b"]})
    assert key["order"] == ["c", "a", "b"]
    with pytest.raises(ValidationFailedError):
        validate(T.ORDERING, {"items": items}, {"order": ["a", "b"]})


def test_coding_needs_a_code_execution_problem_id():
    body, key = validate(T.CODING, {"problem_id": "1755000000006555", "languages": ["python", "java"]}, {})
    assert body["languages"] == ["java", "python"] and key == {"scoring": "partial"}
    with pytest.raises(ValidationFailedError):
        validate(T.CODING, {"problem_id": "12"}, {})


def test_subjective_and_file_rubrics_are_checked():
    body, _ = validate(T.SUBJECTIVE, {"rubric": [{"id": "r1", "criterion": "Clarity", "max_marks": 5}], "max_words": 200}, {})
    assert body["rubric"][0]["max_marks"] == 5.0
    with pytest.raises(ValidationFailedError):
        validate(T.SUBJECTIVE, {"rubric": [{"id": "r1", "criterion": "Clarity", "max_marks": 0}]}, {})
    body, key = validate(T.FILE_SUBMISSION, {"allowed_extensions": [".PDF", "zip"], "max_files": 2}, {})
    assert body["allowed_extensions"] == ["pdf", "zip"] and key == {}


def test_empty_answers_are_a_cleared_answer():
    assert answer(T.MCQ_SINGLE, MCQ_BODY, None) is None
    assert answer(T.MCQ_SINGLE, MCQ_BODY, {"selected": None}) is None
    assert answer(T.MCQ_MULTI, MCQ_BODY, {"selected": []}) is None
    assert answer(T.SUBJECTIVE, {}, {"text": "   "}) is None
    assert answer(T.FILL_IN, {"blanks": 2}, {"values": ["", None]}) is None


def test_mcq_answers_must_use_real_option_ids():
    assert answer(T.MCQ_SINGLE, MCQ_BODY, {"selected": "a"}) == {"selected": "a"}
    assert answer(T.MCQ_MULTI, MCQ_BODY, {"selected": ["c", "a"]}) == {"selected": ["a", "c"]}
    with pytest.raises(ValidationFailedError):
        answer(T.MCQ_SINGLE, MCQ_BODY, {"selected": "z"})
    with pytest.raises(ValidationFailedError):
        answer(T.MCQ_MULTI, MCQ_BODY, {"selected": ["a", "a"]})


def test_ordering_answer_must_include_every_item():
    body = {"items": [{"id": "a", "text": "1"}, {"id": "b", "text": "2"}]}
    assert answer(T.ORDERING, body, {"order": ["b", "a"]}) == {"order": ["b", "a"]}
    with pytest.raises(ValidationFailedError):
        answer(T.ORDERING, body, {"order": ["b"]})


def test_code_answer_language_must_be_allowed_for_the_question():
    body = {"problem_id": "1755000000006555", "languages": ["python"]}
    assert answer(T.CODING, body, {"language": "python", "source": "print(1)"}) == {"language": "python", "source": "print(1)"}
    with pytest.raises(ValidationFailedError):
        answer(T.CODING, body, {"language": "java", "source": "class A {}"})


def test_subjective_word_limit_is_enforced():
    body = {"rubric": [], "max_words": 3}
    assert answer(T.SUBJECTIVE, body, {"text": "one two three"}) == {"text": "one two three"}
    with pytest.raises(ValidationFailedError):
        answer(T.SUBJECTIVE, body, {"text": "one two three four"})


def test_files_must_be_uploaded_for_this_question_and_match_the_rules():
    body = {"allowed_extensions": ["pdf"], "max_files": 1, "max_size_mb": 1}
    prefix = "attempts/1/2/"
    good = {"files": [{"key": prefix + "abc/report.pdf", "filename": "report.pdf", "size": 1000}]}
    assert answer(T.FILE_SUBMISSION, body, good, file_prefix=prefix)["files"][0]["filename"] == "report.pdf"
    stolen = {"files": [{"key": "attempts/9/9/x/report.pdf", "filename": "report.pdf", "size": 1000}]}
    with pytest.raises(ValidationFailedError):
        answer(T.FILE_SUBMISSION, body, stolen, file_prefix=prefix)
    wrong_type = {"files": [{"key": prefix + "abc/a.exe", "filename": "a.exe", "size": 10}]}
    with pytest.raises(ValidationFailedError):
        answer(T.FILE_SUBMISSION, body, wrong_type, file_prefix=prefix)
    too_big = {"files": [{"key": prefix + "abc/a.pdf", "filename": "a.pdf", "size": 5 * 1024 * 1024}]}
    with pytest.raises(ValidationFailedError):
        answer(T.FILE_SUBMISSION, body, too_big, file_prefix=prefix)


def test_oversized_answers_are_refused():
    with pytest.raises(ValidationFailedError):
        normalize_answer(T.SUBJECTIVE, {}, {"text": "x" * 2000}, max_bytes=1024)
