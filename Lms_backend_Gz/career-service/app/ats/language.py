"""Grammar and tone checks that need no model: the mistakes and habits that make a resume weaker, found by rules.

A model can polish wording (``/ai/polish``); these rules are the part that is always available, free and explainable.
"""

import re
from dataclasses import dataclass

# strong verbs a bullet can start with (past or present tense); not exhaustive — a bullet that starts with another verb is not "wrong"
ACTION_VERBS = frozenset(
    """achieved administered analysed analyzed architected assembled audited authored automated boosted built calculated championed collaborated completed
    configured consolidated constructed contributed converted coordinated created customised customized debugged decreased delivered demonstrated deployed
    designed detected developed devised directed documented drove eliminated enabled engineered enhanced established evaluated exceeded executed expanded
    facilitated fixed formulated founded generated guided identified implemented improved increased initiated integrated introduced investigated launched led
    maintained managed mentored migrated modelled modeled monitored negotiated optimised optimized orchestrated organised organized outperformed overhauled
    owned partnered performed pioneered planned presented processed produced programmed proposed prototyped published reduced refactored released remodelled
    replaced reported researched resolved restructured reviewed revised scaled scheduled secured shipped simplified solved spearheaded standardised standardized
    streamlined strengthened supervised supported surpassed taught tested trained transformed translated tuned upgraded validated visualised visualized wrote""".split()
)
_WEAK_STARTS = ("responsible for", "worked on", "helped with", "helped to", "duties included", "tasked with", "involved in", "assisted in", "in charge of")
_FIRST_PERSON = re.compile(r"\b(i|me|my|myself|i'm|i've)\b", re.IGNORECASE)
_REPEAT = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)
_DOUBLE_SPACE = re.compile(r"\S {2,}\S")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+[,.;:!?]")
_NUMBER = re.compile(r"\d")
_FILLER = ("very", "really", "various", "many", "several", "etc", "stuff", "things", "a lot of", "hard-working", "hardworking", "team player", "go-getter", "detail-oriented")
_BUZZ = ("synergy", "rockstar", "ninja", "guru", "passionate about", "results-driven", "self-motivated", "think outside the box")


@dataclass(frozen=True, slots=True)
class Issue:
    code: str
    severity: str  # "error" | "warning" | "tip"
    message: str
    excerpt: str


def first_word(text: str) -> str:
    match = re.match(r"[A-Za-z]+", text.strip())
    return match.group(0).lower() if match else ""


def starts_with_action_verb(bullet: str) -> bool:
    return first_word(bullet) in ACTION_VERBS


def is_quantified(bullet: str) -> bool:
    return bool(_NUMBER.search(bullet))


def check_text(text: str) -> list[Issue]:
    """Issues in one piece of text (a bullet, a summary): mechanics first, then tone."""
    issues: list[Issue] = []
    body = text.strip()
    if not body:
        return issues
    if _DOUBLE_SPACE.search(body):
        issues.append(Issue("DOUBLE_SPACE", "warning", "Two spaces in a row.", body[:80]))
    if _SPACE_BEFORE_PUNCT.search(body):
        issues.append(Issue("SPACE_BEFORE_PUNCTUATION", "warning", "A space before punctuation.", body[:80]))
    for match in _REPEAT.finditer(body):
        issues.append(Issue("REPEATED_WORD", "error", f"The word “{match.group(1)}” is repeated.", match.group(0)))
    if _FIRST_PERSON.search(body):
        issues.append(Issue("FIRST_PERSON", "warning", "Resumes drop “I” and “my”: start with the action instead.", body[:80]))
    lowered = body.lower()
    for weak in _WEAK_STARTS:
        if lowered.startswith(weak):
            issues.append(Issue("WEAK_OPENING", "warning", f"“{weak.capitalize()}” hides what you did. Start with a verb like Built, Led or Reduced.", body[:80]))
            break
    for word in _FILLER:
        if re.search(rf"\b{re.escape(word)}\b", lowered):
            issues.append(Issue("FILLER", "tip", f"“{word}” adds no information; say what, how many or how much.", body[:80]))
    for word in _BUZZ:
        if word in lowered:
            issues.append(Issue("BUZZWORD", "tip", f"“{word}” is a buzzword; show it with a fact instead.", body[:80]))
    if body[0].islower() and not body.startswith(("http://", "https://", "www.")):
        issues.append(Issue("LOWERCASE_START", "warning", "Start with a capital letter.", body[:80]))
    if len(body) > 260:
        issues.append(Issue("TOO_LONG", "tip", "Long lines are hard to skim: aim for one or two lines.", body[:80]))
    return issues
