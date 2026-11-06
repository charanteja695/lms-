"""The rule that the AI never invents credentials (docs/PRODUCT.md §5.6), enforced in code.

A model is asked to rewrite or summarise what a student really has, and told not to add anything. Told is not enough: every
suggestion is compared with the facts it was made from, and anything that appears in the output but not in the source — a
number, a link, an email address, a capitalised name, a keyword the job description wants — is reported as a warning, and the
suggestion is marked not applicable. Nothing from a model is ever saved by this service: the student applies a suggestion by
saving their own edit.
"""

import re
from dataclasses import dataclass

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+#.\-]*")
_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+|\n\s*[-•*]?\s*)([A-Za-z][A-Za-z0-9+#.\-]*)")
# capitalised words a good rewrite may contain without them being new facts
_COMMON = frozenset("i a an the and or of in on for to with by at as from is are was were be been it its this that these those my our their".split())


@dataclass(frozen=True, slots=True)
class Finding:
    kind: str  # "number" | "url" | "email" | "name" | "keyword"
    value: str

    def as_dict(self) -> dict[str, str]:
        return {"type": self.kind, "value": self.value}


def _numbers(text: str) -> set[str]:
    return {m.group(0).replace(",", "").rstrip(".") for m in _NUMBER.finditer(text)}


def _sentence_starts(text: str) -> set[str]:
    return {m.group(1).lower() for m in _SENTENCE_START.finditer(text)}


def _names(text: str) -> set[str]:
    """Capitalised words that are not merely the first word of a sentence or bullet: names, products, technologies, acronyms."""
    starts = _sentence_starts(text)
    found = set()
    for match in _WORD.finditer(text):
        word = match.group(0).strip(".-")
        if len(word) < 2 or not (word[0].isupper() or word.isupper()):
            continue
        if word.lower() in _COMMON:
            continue
        if word.lower() in starts and not word.isupper() and text.count(word) == 1:
            continue  # only ever seen opening a sentence: an ordinary capital letter
        found.add(word.lower())
    return found


def invented(source: str, output: str, *, allowed_keywords: frozenset[str] = frozenset()) -> list[Finding]:
    """What ``output`` says that ``source`` does not. ``allowed_keywords`` are terms the output may use even though the source lacks
    them (used never for tailoring: a keyword the student does not have must not be added)."""
    warnings: list[Finding] = []
    src_numbers = _numbers(source)
    for number in sorted(_numbers(output) - src_numbers):
        warnings.append(Finding("number", number))
    for url in sorted({u.rstrip(".,)") for u in _URL.findall(output)} - {u.rstrip(".,)") for u in _URL.findall(source)}):
        warnings.append(Finding("url", url))
    for email in sorted(set(_EMAIL.findall(output)) - set(_EMAIL.findall(source))):
        warnings.append(Finding("email", email))
    src_lower = source.lower()
    src_names = _names(source)
    for name in sorted(_names(output) - src_names):
        if name not in src_lower and name not in allowed_keywords:
            warnings.append(Finding("name", name))
    return warnings


def unsupported_keywords(source: str, output: str, keywords: list[str]) -> list[Finding]:
    """Job-description keywords that the output contains but the facts it was written from do not."""
    src, out = source.lower(), output.lower()
    return [Finding("keyword", k) for k in keywords if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", out) and not re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", src)]
