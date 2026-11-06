"""Reading a student's message for what the tutor must not answer itself (docs/PRODUCT.md §5.5 "Escalation"):
a request for a person, or a matter of money, integrity or account access. Pure functions over text.

Keyword rules, not a classifier — so they are conservative in two directions: a first-person framing is required in a
learning conversation (a course *about* payment gateways must not escalate "how does a payment gateway work"), while
the support assistant, whose whole job is the student's own account, matches more loosely.
"""

import re

from app.domain.enums import ConversationMode, EscalationCategory

_HUMAN = re.compile(
    r"\b(talk|speak|chat|connect|escalate|transfer|hand)(\s+(me|this))?(\s+(to|with|over to))?\s+(a\s+|an\s+|the\s+|your\s+|my\s+)?"
    r"(human|real person|person|teacher|instructor|tutor|staff|agent|support|someone|mentor|faculty|professor)\b"
    r"|\b(human|real person|live)\s+(agent|support|help)\b|\bi\s+(really\s+|just\s+)?(want|need|would like)\s+(to\s+(talk|speak)\s+to\s+)?(a\s+)?(human|person|teacher|someone)\b",
    re.IGNORECASE,
)

# Matters the tutor never resolves. The first set applies to every conversation and is first-person or unambiguous.
_STRICT: dict[EscalationCategory, re.Pattern[str]] = {
    EscalationCategory.BILLING: re.compile(
        r"\b(refund|money back|chargeback|charged me|double charged|overcharged|my (payment|fee|fees|invoice|receipt|subscription))\b",
        re.IGNORECASE,
    ),
    EscalationCategory.INTEGRITY: re.compile(
        r"\b(accused of cheating|marked (me )?as cheating|flagged (me )?for|malpractice|my (attempt|test|exam) (was|got|is) (invalidated|cancelled|terminated|flagged)|"
        r"integrity (case|review|decision)|proctor(ing)? (flagged|terminated|cancelled)|appeal (my|the) (attempt|result|decision))\b",
        re.IGNORECASE,
    ),
    EscalationCategory.ACCESS: re.compile(
        r"\b(locked out|can'?t log ?in|cannot log ?in|unable to log ?in|my account (is |was |has been )?(suspended|locked|blocked|disabled|deleted)|"
        r"(removed|dropped) from (the |my )?(course|batch|class)|lost access|no access to (the |my )?course)\b",
        re.IGNORECASE,
    ),
}
# The support assistant also takes looser phrasings of the same three matters.
_SUPPORT_EXTRA: dict[EscalationCategory, re.Pattern[str]] = {
    EscalationCategory.BILLING: re.compile(r"\b(refund|payment|paid|invoice|billing|fees?|price|receipt|gst)\b", re.IGNORECASE),
    EscalationCategory.INTEGRITY: re.compile(r"\b(cheat\w*|malpractice|proctor\w*|flagged|integrity|invalidated|plagiar\w*)\b", re.IGNORECASE),
    EscalationCategory.ACCESS: re.compile(r"\b(log ?in|password|suspended|locked|blocked|access|seat)\b", re.IGNORECASE),
}

_ENROLMENT = re.compile(r"\b(enrol\w*|enroll\w*|batch|my courses?|course access|seat|cannot see (the )?course|can'?t (see|open) (the )?course)\b", re.IGNORECASE)
_ATTEMPT = re.compile(r"\b(test|exam|attempt|quiz|score|result|marks|re-?attempt|passed|failed|grade)\b", re.IGNORECASE)
_CERTIFICATE = re.compile(r"\b(certificate|certif\w*|completion)\b", re.IGNORECASE)
_SOLUTION = re.compile(
    r"\b(give|show|tell|write|send)\s+(me\s+)?(the\s+)?(full\s+|complete\s+|whole\s+|final\s+)?(solution|answer|code)\b|\bjust\s+(give|show|tell)\b|"
    r"\bsolve\s+(it|this)\s+for\s+me\b|\bfull\s+(code|solution)\b",
    re.IGNORECASE,
)
_CITATION = re.compile(r"\[(\d{1,2})\]")


def asks_for_human(text: str) -> bool:
    return _HUMAN.search(text) is not None


def sensitive_category(text: str, mode: ConversationMode) -> EscalationCategory | None:
    """The category a message falls under, if it is a matter the tutor must hand to a person."""
    for category, pattern in _STRICT.items():
        if pattern.search(text):
            return category
    if mode == ConversationMode.SUPPORT:
        for category, pattern in _SUPPORT_EXTRA.items():
            if pattern.search(text):
                return category
    return None


def lookups_wanted(text: str) -> set[str]:
    """Which read-only lookups (docs/PRODUCT.md §5.5: enrolment, attempt, certificate status) a support question needs."""
    wanted = set()
    if _ENROLMENT.search(text):
        wanted.add("enrolment")
    if _ATTEMPT.search(text):
        wanted.add("attempts")
    if _CERTIFICATE.search(text):
        wanted.add("certificates")
    return wanted


def asks_for_solution(text: str) -> bool:
    return _SOLUTION.search(text) is not None


def cited_numbers(answer: str) -> list[int]:
    """The ``[n]`` source numbers an answer refers to, in order of first appearance."""
    seen: list[int] = []
    for match in _CITATION.finditer(answer):
        number = int(match.group(1))
        if number not in seen:
            seen.append(number)
    return seen
