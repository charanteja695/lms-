"""What goes on a certificate, independent of how it is drawn: the placeholders a template may use, the built-in
default template, and how a score becomes a grade band."""

import re
import string
from typing import Any

from app.core.exceptions import ValidationFailedError

PLACEHOLDERS = frozenset(
    {"student_name", "course_title", "completion_date", "institution_name", "score_percent", "grade", "issuer", "certificate_id"}
)
_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")

DEFAULT_GRADE_BANDS: list[dict[str, Any]] = [
    {"min_percent": 85, "label": "Distinction"},
    {"min_percent": 70, "label": "Merit"},
    {"min_percent": 0, "label": "Pass"},
]

DEFAULT_TEMPLATE: dict[str, Any] = {
    "name": "Default",
    "title_text": "Certificate of Completion",
    "body_text": "This is to certify that\n{student_name}\nhas successfully completed the course\n{course_title}\nwith a score of {score_percent}% ({grade}).",
    "footer_text": "Issued by {issuer}. Verify this certificate by scanning the QR code.",
    "accent_color": "#1F4E79",
    "signatories": [],
    "grade_bands": DEFAULT_GRADE_BANDS,
}


def placeholders_in(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def validate_text_placeholders(field: str, text: str | None) -> None:
    if not text:
        return
    try:
        unknown = sorted(placeholders_in(text) - PLACEHOLDERS)
    except ValueError as exc:  # an unbalanced brace
        raise ValidationFailedError(details=[{"field": field, "code": "INVALID_PLACEHOLDER", "message": str(exc)}]) from exc
    if unknown:
        allowed = ", ".join("{" + name + "}" for name in sorted(PLACEHOLDERS))
        raise ValidationFailedError(
            details=[{"field": field, "code": "INVALID_PLACEHOLDER", "message": f"Unknown placeholders {unknown}; use {allowed}"}]
        )


def validate_color(value: str) -> str:
    if not _COLOR.fullmatch(value):
        raise ValidationFailedError(details=[{"field": "accent_color", "code": "INVALID_COLOR", "message": "Use #RRGGBB"}])
    return value.upper()


def validate_bands(bands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Best band first; the last must start at 0 so every score has a grade."""
    cleaned: list[dict[str, Any]] = sorted(
        ({"min_percent": int(b["min_percent"]), "label": str(b["label"]).strip()} for b in bands), key=lambda b: -b["min_percent"]
    )
    if not cleaned or cleaned[-1]["min_percent"] != 0:
        raise ValidationFailedError(details=[{"field": "grade_bands", "code": "INVALID_BANDS", "message": "The lowest band must start at 0"}])
    if len({b["min_percent"] for b in cleaned}) != len(cleaned):
        raise ValidationFailedError(details=[{"field": "grade_bands", "code": "INVALID_BANDS", "message": "Two bands start at the same percent"}])
    return cleaned


def grade_for(percent: float, bands: list[dict[str, Any]]) -> str | None:
    for band in sorted(bands, key=lambda b: -b["min_percent"]):
        if percent >= band["min_percent"]:
            return str(band["label"])
    return None


class _Blank(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""


def fill(text: str, values: dict[str, str]) -> str:
    """Substitute placeholders; a missing value leaves nothing behind (an empty grade prints no empty brackets)."""
    filled = string.Formatter().vformat(text, (), _Blank(values))
    return re.sub(r"[ \t]*\(\s*\)", "", filled).strip()
