"""Checks and normalises a student's answer against the question it answers. Returns ``None`` when the answer is
empty (a cleared answer), otherwise the normalised response that is stored and graded.

  mcq_single       {selected: "id"}
  mcq_multi        {selected: ["id", ...]}
  true_false       {value: true|false}
  fill_in          {values: ["text" | null, ...]}      one entry per blank
  match            {pairs: {leftId: rightId}}
  ordering         {order: ["id", ...]}                 every item, in the student's order
  coding | sql     {language: "python", source: "..."}
  subjective       {text: "..."}
  file_submission  {files: [{key, filename, size, content_type}]}   keys come from POST .../file-upload-url
"""

import json
from typing import Any

from app.core.exceptions import ValidationFailedError
from app.domain.enums import QuestionType

MAX_FILL_LENGTH = 500
MAX_TEXT_CHARS = 100_000


def _invalid(message: str, field: str = "response") -> ValidationFailedError:
    return ValidationFailedError(details=[{"field": field, "code": "INVALID_ANSWER", "message": message}])


def _ids(body_items: list[dict[str, Any]]) -> set[str]:
    return {item["id"] for item in body_items}


def normalize_answer(
    qtype: QuestionType,
    body: dict[str, Any],
    response: dict[str, Any] | None,
    *,
    max_bytes: int,
    file_prefix: str | None = None,
) -> dict[str, Any] | None:
    if response is None or response == {}:
        return None
    if not isinstance(response, dict):
        raise _invalid("Must be an object")
    if len(json.dumps(response, ensure_ascii=False).encode()) > max_bytes:
        raise _invalid(f"The answer is larger than {max_bytes} bytes")
    match qtype:
        case QuestionType.MCQ_SINGLE:
            return _mcq_single(body, response)
        case QuestionType.MCQ_MULTI:
            return _mcq_multi(body, response)
        case QuestionType.TRUE_FALSE:
            value = response.get("value")
            if value is None:
                return None
            if not isinstance(value, bool):
                raise _invalid("value must be true or false", "response.value")
            return {"value": value}
        case QuestionType.FILL_IN:
            return _fill_in(body, response)
        case QuestionType.MATCH:
            return _match(body, response)
        case QuestionType.ORDERING:
            return _ordering(body, response)
        case QuestionType.CODING | QuestionType.SQL:
            return _judged(body, response)
        case QuestionType.SUBJECTIVE:
            return _subjective(body, response)
        case _:
            return _files(body, response, file_prefix)


def _mcq_single(body: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    selected = response.get("selected")
    if selected is None or selected == "":
        return None
    if not isinstance(selected, str) or selected not in _ids(body["options"]):
        raise _invalid("selected must be the id of one of the options", "response.selected")
    return {"selected": selected}


def _mcq_multi(body: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    selected = response.get("selected")
    if selected is None or selected == []:
        return None
    if (
        not isinstance(selected, list)
        or len(set(selected)) != len(selected)
        or not all(isinstance(value, str) and value in _ids(body["options"]) for value in selected)
    ):
        raise _invalid("selected must list distinct option ids", "response.selected")
    return {"selected": sorted(selected)}


def _fill_in(body: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    values = response.get("values")
    if values is None:
        return None
    if not isinstance(values, list) or len(values) != body["blanks"]:
        raise _invalid(f"values needs one entry for each of the {body['blanks']} blanks", "response.values")
    cleaned: list[str | None] = []
    for value in values:
        if value is not None and (not isinstance(value, str) or len(value) > MAX_FILL_LENGTH):
            raise _invalid(f"Each value must be text of at most {MAX_FILL_LENGTH} characters", "response.values")
        cleaned.append(value.strip() if isinstance(value, str) and value.strip() else None)
    return None if all(value is None for value in cleaned) else {"values": cleaned}


def _match(body: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    pairs = response.get("pairs")
    if pairs is None or pairs == {}:
        return None
    left, right = _ids(body["left"]), _ids(body["right"])
    if (
        not isinstance(pairs, dict)
        or not set(pairs) <= left
        or not all(isinstance(value, str) and value in right for value in pairs.values())
        or len(set(pairs.values())) != len(pairs)
    ):
        raise _invalid("pairs must map distinct left ids to distinct right ids", "response.pairs")
    return {"pairs": dict(pairs)}


def _ordering(body: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    order = response.get("order")
    if order is None or order == []:
        return None
    if not isinstance(order, list) or sorted(order, key=str) != sorted(_ids(body["items"])):
        raise _invalid("order must list every item exactly once", "response.order")
    return {"order": order}


def _judged(body: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    language, source = response.get("language"), response.get("source")
    if source is None or (isinstance(source, str) and not source.strip()):
        return None
    if not isinstance(language, str) or not isinstance(source, str):
        raise _invalid("language and source must be text")
    allowed = body.get("languages")
    if allowed and language not in allowed:
        raise _invalid(f"language must be one of: {', '.join(allowed)}", "response.language")
    if chr(0) in source:
        raise _invalid("source must not contain NUL characters", "response.source")
    return {"language": language, "source": source}


def _subjective(body: dict[str, Any], response: dict[str, Any]) -> dict[str, Any] | None:
    text = response.get("text")
    if text is None or (isinstance(text, str) and not text.strip()):
        return None
    if not isinstance(text, str) or len(text) > MAX_TEXT_CHARS:
        raise _invalid(f"text must be at most {MAX_TEXT_CHARS} characters", "response.text")
    max_words = body.get("max_words")
    if max_words and len(text.split()) > max_words:
        raise _invalid(f"The answer is limited to {max_words} words", "response.text")
    return {"text": text}


def _files(body: dict[str, Any], response: dict[str, Any], file_prefix: str | None) -> dict[str, Any] | None:
    files = response.get("files")
    if files is None or files == []:
        return None
    if not isinstance(files, list) or len(files) > body["max_files"]:
        raise _invalid(f"At most {body['max_files']} files can be attached", "response.files")
    allowed = body.get("allowed_extensions")
    limit_bytes = body["max_size_mb"] * 1024 * 1024
    cleaned: list[dict[str, Any]] = []
    for entry in files:
        key = entry.get("key") if isinstance(entry, dict) else None
        filename = entry.get("filename") if isinstance(entry, dict) else None
        size = entry.get("size") if isinstance(entry, dict) else None
        if not isinstance(key, str) or not file_prefix or not key.startswith(file_prefix) or ".." in key:
            raise _invalid("Attach only files uploaded for this question", "response.files")
        if not isinstance(filename, str) or not filename or len(filename) > 200:
            raise _invalid("Each file needs a filename of up to 200 characters", "response.files")
        if isinstance(size, bool) or not isinstance(size, int) or not 0 < size <= limit_bytes:
            raise _invalid(f"Each file must be up to {body['max_size_mb']} MB", "response.files")
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if allowed and extension not in allowed:
            raise _invalid(f"Allowed file types: {', '.join(allowed)}", "response.files")
        content_type = entry.get("content_type")
        cleaned.append(
            {
                "key": key,
                "filename": filename,
                "size": size,
                "content_type": content_type if isinstance(content_type, str) else "application/octet-stream",
            }
        )
    return {"files": cleaned}
