"""PII redaction (docs/PRODUCT.md §5.5: "PII is redacted before calls to the model").

A small set of regexes, not an ML model: it catches the common, structured forms of PII (emails, phone numbers,
card-like and government-id-like number sequences) that show up when a student pastes an error message or their
own profile text into a chat. It does not catch names or addresses in free text — no regex can. Applied to every
outbound message *before* it reaches a provider, and the redacted text (never the original) is what gets logged
in ``AiCallLog.request_redacted``.
"""

import re
from dataclasses import dataclass, field

_PATTERNS: dict[str, re.Pattern[str]] = {
    "pii:email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "pii:phone": re.compile(r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?\d{10}(?!\d)"),
    "pii:aadhaar": re.compile(r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)"),  # India's 12-digit id (spaced in 4s)
    "pii:pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),  # India's PAN
    "pii:card": re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
}
# Order matters: a card-like or Aadhaar-like run of digits would also match the phone pattern, so check the more
# specific (longer) patterns first and let a match consume its span before a looser one is tried on what's left.
_ORDER = ("pii:email", "pii:pan", "pii:card", "pii:aadhaar", "pii:phone")


@dataclass(slots=True)
class Redacted:
    text: str
    flags: set[str] = field(default_factory=set)


def redact_text(text: str) -> Redacted:
    flags: set[str] = set()
    for flag in _ORDER:
        pattern = _PATTERNS[flag]

        def _replace(match: re.Match[str], flag: str = flag) -> str:
            flags.add(flag)
            return f"[REDACTED_{flag.split(':', 1)[1].upper()}]"

        text = pattern.sub(_replace, text)
    return Redacted(text=text, flags=flags)


def redact_messages(messages: list[dict[str, str]]) -> tuple[list[dict[str, str]], set[str]]:
    """Redact every message's ``content``; other fields (``role``, ...) pass through unchanged."""
    flags: set[str] = set()
    redacted: list[dict[str, str]] = []
    for message in messages:
        result = redact_text(message.get("content", ""))
        flags |= result.flags
        redacted.append({**message, "content": result.text})
    return redacted, flags
