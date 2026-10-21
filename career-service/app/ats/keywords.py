"""Keyword gap analysis: which words a job description leans on, and which of them a resume already says.

Deterministic on purpose. A ranked list of terms with the reason they matter is something a student can act on and check; a
model's opinion is not. Matching is on normalised words (case, a trailing plural), not meaning — the same limits an
applicant tracking system has, which is exactly what an "ATS score" should reflect.
"""

import re
from collections import Counter
from dataclasses import dataclass

# words that appear in every job description and say nothing about the job
_STOP = frozenset(
    """a about above across after all also am an and any are as at be been being both but by can could did do does doing done during each either etc
    few for from further had has have having he her here hers him his how i if in into is it its just like may me might more most much must my no nor
    not of off on once one only or other our out over own per same shall she should so some such than that the their them then there these they this those
    through to too under until up us use used using very was we were what when where which while who whom why will with within without would you your yours
    ability able about abilities across additional applicant applicants apply based benefits candidate candidates career company preferred required requirements
    responsibilities role roles skills skill strong team teams work working worked works year years experience experienced excellent good great looking
    opportunity opportunities plus position positions qualifications knowledge understanding etc including include includes join environment fast paced
    ensure ensuring support new well building build across various related relevant minimum degree bachelor bachelors master masters equivalent need needs needed essential important seeking want wanted ideal hiring hire looking day every daily
    matter matters comfortable familiar familiarity proficient proficiency hands solid nice bonus get make makes help helps let lets someone person people
    please send email resume cv salary location office remote hybrid onsite full time part""".split()
)
_TOKEN = re.compile(r"[a-z][a-z0-9+#.\-]*[a-z0-9+#]|[a-z]")
_TRIM = ".-"


def normalise(word: str) -> str:
    word = word.strip(_TRIM).lower()
    if len(word) > 3 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss") and not word.endswith("us"):
        return word[:-1]
    return word


def tokens(text: str) -> list[str]:
    return [normalise(t) for t in _TOKEN.findall(text.lower()) if normalise(t)]


@dataclass(frozen=True, slots=True)
class Keyword:
    term: str
    weight: int  # how many times the job description says it
    present: bool


def job_keywords(job_description: str, *, limit: int = 30) -> list[tuple[str, int]]:
    """The terms a job description leans on, most frequent first: single words, and two-word phrases said at least twice.
    Terms are shown as the job description wrote them (lower-cased), not in their normalised matching form."""
    surfaces = [(normalise(t), t.strip(_TRIM)) for t in _TOKEN.findall(job_description.lower())]
    surfaces = [(n, t) for n, t in surfaces if n]
    counts: Counter[str] = Counter()
    shown: dict[str, str] = {}
    for norm, surface in surfaces:
        if norm not in _STOP and len(norm) > 1:
            counts[norm] += 1
            shown.setdefault(norm, surface)
    for (n1, t1), (n2, t2) in zip(surfaces, surfaces[1:], strict=False):
        if n1 not in _STOP and n2 not in _STOP and len(n1) > 1 and len(n2) > 1:
            counts[f"{n1} {n2}"] += 1
            shown.setdefault(f"{n1} {n2}", f"{t1} {t2}")
    ranked = [(norm, n) for norm, n in counts.items() if " " not in norm or n >= 2]
    ranked.sort(key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))
    return [(shown[norm], n) for norm, n in ranked[:limit]]


def coverage(job_description: str, resume_text: str, *, limit: int = 30) -> list[Keyword]:
    haystack_words = tokens(resume_text)
    haystack = " ".join(haystack_words)
    result = []
    for term, weight in job_keywords(job_description, limit=limit):
        found = f" {' '.join(tokens(term))} " in f" {haystack} "
        result.append(Keyword(term=term, weight=weight, present=found))
    return result
