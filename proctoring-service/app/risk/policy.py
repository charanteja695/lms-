"""Risk scoring (docs/PRODUCT.md §5.3: "each event has a weight, which produces a live risk score").

Pure and table-driven, so the policy is one screen of data and every rule is a plain unit test. Each event type adds
``weight`` points per occurrence but never more than ``cap`` points in total, so a student whose browser loses focus fifty
times does not outweigh one seen with a second person in the room; the score is capped at 100.

``critical`` events are the ones that always put a human in the loop, whatever the score: nothing here (or anywhere in
this service) ever invalidates an attempt on its own.
"""

from dataclasses import dataclass
from typing import Literal

Source = Literal["client", "ai", "system", "staff"]
Level = Literal["basic", "strict"]


@dataclass(frozen=True, slots=True)
class EventRule:
    weight: int
    cap: int
    sources: frozenset[Source]
    min_level: Level = "basic"
    critical: bool = False


_C: frozenset[Source] = frozenset({"client"})
_A: frozenset[Source] = frozenset({"ai"})
_S: frozenset[Source] = frozenset({"system"})
_CS: frozenset[Source] = frozenset({"client", "system"})

RULES: dict[str, EventRule] = {
    # Browser events, reported by the client (basic and strict)
    "fullscreen_exit": EventRule(8, 40, _C),
    "tab_switch": EventRule(6, 30, _C),
    "window_blur": EventRule(3, 15, _C),
    "copy_paste": EventRule(5, 20, _C),
    "right_click": EventRule(1, 5, _C),
    "devtools_open": EventRule(15, 30, _C),
    "multiple_monitors": EventRule(10, 10, _C),
    "network_lost": EventRule(2, 10, _C),
    # Strict only: media state reported by the client
    "camera_off": EventRule(10, 30, _C, "strict"),
    "mic_off": EventRule(4, 12, _C, "strict"),
    "screen_share_stopped": EventRule(10, 20, _C, "strict"),
    # Raised by this service
    "multiple_sessions": EventRule(20, 40, _S),
    "device_changed": EventRule(15, 15, _S),
    "ip_changed": EventRule(5, 10, _S),
    "heartbeat_lost": EventRule(6, 30, _S),
    "precheck_missing": EventRule(15, 15, _S),
    "warned": EventRule(0, 0, frozenset({"staff"})),
    "paused": EventRule(0, 0, frozenset({"staff"})),
    "terminated": EventRule(50, 50, frozenset({"staff"}), critical=True),
    # Raised from AI analysis of snapshots and audio (strict only)
    "no_face": EventRule(10, 30, _A, "strict"),
    "multiple_faces": EventRule(25, 50, _A, "strict", critical=True),
    "different_person": EventRule(40, 40, _A, "strict", critical=True),
    "identity_mismatch": EventRule(40, 40, _A, "strict", critical=True),
    "phone_detected": EventRule(20, 40, _A, "strict"),
    "book_detected": EventRule(8, 16, _A, "strict"),
    "looking_away": EventRule(4, 20, _A, "strict"),
    "voices_detected": EventRule(10, 30, _A, "strict"),
}

CLIENT_EVENT_TYPES = frozenset(name for name, rule in RULES.items() if "client" in rule.sources)
AI_FINDING_TYPES = frozenset(name for name, rule in RULES.items() if "ai" in rule.sources)
MAX_SCORE = 100


def allowed(event_type: str, source: Source, level: Level) -> bool:
    """May ``source`` report ``event_type`` in a session of ``level``? (A basic session takes no camera/AI events.)"""
    rule = RULES.get(event_type)
    if rule is None or source not in rule.sources:
        return False
    return not (rule.min_level == "strict" and level == "basic")


def points(event_type: str, already: int, *, scale: float = 1.0) -> int:
    """The points this occurrence adds given what the type has already contributed (never past its cap)."""
    rule = RULES[event_type]
    return max(0, min(round(rule.weight * scale), rule.cap - already))


def score_of(breakdown: dict[str, int]) -> int:
    return min(MAX_SCORE, sum(breakdown.values()))


def severity(score: int, *, clear_max: int, flag_min: int) -> str:
    if score <= clear_max:
        return "low"
    return "high" if score >= flag_min else "medium"


def is_critical(event_type: str) -> bool:
    rule = RULES.get(event_type)
    return bool(rule and rule.critical)
