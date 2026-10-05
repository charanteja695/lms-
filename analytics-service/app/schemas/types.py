"""Validated field types used across request/response schemas (see user-management's
``app/schemas/types.py`` for the full pattern this trims down to what this service needs)."""

import re
import unicodedata
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BeforeValidator, PlainSerializer, WithJsonSchema
from pydantic_core import PydanticCustomError

from app.core.ids import parse_public_id

_BIDI_CONTROLS = frozenset("‪‫‬‭‮⁦⁧⁨⁩")
_WHITESPACE_RUN = re.compile(r"\s+")
_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{1,78}[a-z0-9]$")


def _error(code: str, message: str) -> PydanticCustomError:
    return PydanticCustomError(code, message)


def _require_str(value: Any) -> str:
    if not isinstance(value, str):
        raise _error("INVALID_TYPE", "Must be a string")
    return value


def _clean_text(value: str, *, min_length: int, max_length: int) -> str:
    value = _WHITESPACE_RUN.sub(" ", unicodedata.normalize("NFC", value)).strip()
    for char in value:
        if char in _BIDI_CONTROLS or unicodedata.category(char) in {"Cc", "Cs", "Co"}:
            raise _error("INVALID_CHARACTERS", "Must not contain control or invisible formatting characters")
    if len(value) < min_length:
        raise _error("REQUIRED" if not value else "TOO_SHORT", f"Must be at least {min_length} characters")
    if len(value) > max_length:
        raise _error("TOO_LONG", f"Must be at most {max_length} characters")
    return value


def _string_type(validator: Any, *, max_length: int, examples: list[str] | None = None, **schema: Any) -> Any:
    json_schema: dict[str, Any] = {"type": "string", "maxLength": max_length, **schema}
    if examples:
        json_schema["examples"] = examples
    return Annotated[str, BeforeValidator(_require_str), AfterValidator(validator), WithJsonSchema(json_schema)]


def text(max_length: int, *, min_length: int = 1, examples: list[str] | None = None) -> Any:
    """Free text: trimmed, whitespace collapsed, Unicode-normalised, no control characters."""
    return _string_type(lambda v: _clean_text(v, min_length=min_length, max_length=max_length), max_length=max_length, minLength=min_length, examples=examples)


def _clean_multiline(value: str, *, min_length: int, max_length: int) -> str:
    value = unicodedata.normalize("NFC", value).replace(chr(13) + chr(10), chr(10)).strip()
    for char in value:
        if char in _BIDI_CONTROLS or (unicodedata.category(char) in {"Cc", "Cs", "Co"} and char != chr(10)):
            raise _error("INVALID_CHARACTERS", "Must not contain control or invisible formatting characters")
    if len(value) < min_length:
        raise _error("REQUIRED" if not value else "TOO_SHORT", f"Must be at least {min_length} characters")
    if len(value) > max_length:
        raise _error("TOO_LONG", f"Must be at most {max_length} characters")
    return value


def multiline_text(max_length: int, *, min_length: int = 1, examples: list[str] | None = None) -> Any:
    """Free text that keeps line breaks (a chat message, a rendered prompt): trimmed, Unicode-normalised, no
    control characters other than newline."""
    return _string_type(lambda v: _clean_multiline(v, min_length=min_length, max_length=max_length), max_length=max_length, minLength=min_length, examples=examples)


def _raw(value: str, *, max_length: int) -> str:
    if len(value) > max_length:
        raise _error("TOO_LONG", f"Must be at most {max_length} characters")
    if chr(0) in value:
        raise _error("INVALID_CHARACTERS", "Must not contain NUL characters")
    return value


def raw_text(max_length: int, *, examples: list[str] | None = None) -> Any:
    """Text kept exactly as sent (code to embed, a message body): whitespace and blank lines are significant."""
    return _string_type(lambda v: _raw(v, max_length=max_length), max_length=max_length, examples=examples)


def _slug(value: str) -> str:
    if not _SLUG_PATTERN.fullmatch(value):
        raise _error("INVALID_SLUG", "Must be lower-case letters, digits, dots, hyphens and underscores, e.g. \"tutor.explain_concept\" or \"ai-tutor-service\"")
    return value


def slug(max_length: int = 80, *, examples: list[str] | None = None) -> Any:
    return _string_type(_slug, max_length=max_length, examples=examples or ["tutor.explain_concept"])


def _id_type(label: str, example: str) -> Any:
    def validate(value: Any) -> int:
        number = parse_public_id(value)
        if number is None:
            raise _error("INVALID_ID", f'Must be a valid {label} (a numeric string such as "{example}")')
        return number

    return Annotated[int, BeforeValidator(validate), WithJsonSchema({"type": "string", "pattern": r"^[1-9][0-9]{9,18}$", "examples": [example]})]


def id_field(label: str, example: str) -> Any:
    return _id_type(label, example)


# Output: 64-bit ids are always serialised as strings (JavaScript numbers lose precision above 2^53).
PublicIdOut = Annotated[int, PlainSerializer(str, return_type=str), WithJsonSchema({"type": "string"})]


def _utc_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


Timestamp = Annotated[datetime, PlainSerializer(_utc_timestamp, return_type=str), WithJsonSchema({"type": "string", "format": "date-time", "examples": ["2026-09-22T10:30:00Z"]})]
