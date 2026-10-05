"""What makes a valid interview plan, and the arithmetic of its time. Pure functions (docs/PRODUCT.md §5.8 "Setup").

Rounds are intro, technical Q&A, live coding, system design (senior roles only) and behavioural. Each round has *core questions*, asked to every
candidate, word for word and in order — that is what makes an interview fair: the same plan and rubric for everyone. The AI adds follow-ups; it
never replaces or reorders the core questions. Each round is scored on the rubric criteria listed for it, and the plan weights the criteria.
"""

from typing import Any

from app.domain.enums import Criterion, Difficulty, PlanKind, RoundType

ROUND_DEFAULT_CRITERIA: dict[RoundType, tuple[Criterion, ...]] = {
    RoundType.INTRO: (Criterion.COMMUNICATION,),
    RoundType.TECHNICAL: (Criterion.TECHNICAL_DEPTH, Criterion.PROBLEM_SOLVING, Criterion.COMMUNICATION),
    RoundType.CODING: (Criterion.PROBLEM_SOLVING, Criterion.CODE_QUALITY, Criterion.TECHNICAL_DEPTH),
    RoundType.SYSTEM_DESIGN: (Criterion.TECHNICAL_DEPTH, Criterion.PROBLEM_SOLVING, Criterion.COMMUNICATION),
    RoundType.BEHAVIOURAL: (Criterion.BEHAVIOURAL, Criterion.COMMUNICATION),
}
MAX_ROUNDS = 6
MIN_ROUND_MINUTES = 3
MAX_DURATION_MINUTES = 90
MIN_DURATION_MINUTES = 10


class PlanError(ValueError):
    def __init__(self, field: str, code: str, message: str) -> None:
        super().__init__(message)
        self.field, self.code, self.message = field, code, message


def normalise(*, kind: PlanKind, difficulty: Difficulty, duration_minutes: int, rounds: list[dict[str, Any]], criteria_weights: dict[str, float] | None) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Validate the rounds and rubric; returns the stored rounds (each with a ``key`` and its ``criteria``) and the criterion weights (summing to 1)."""
    if not MIN_DURATION_MINUTES <= duration_minutes <= MAX_DURATION_MINUTES:
        raise PlanError("duration_minutes", "OUT_OF_RANGE", f"An interview lasts {MIN_DURATION_MINUTES}–{MAX_DURATION_MINUTES} minutes")
    if not 1 <= len(rounds) <= MAX_ROUNDS:
        raise PlanError("rounds", "OUT_OF_RANGE", f"A plan has 1–{MAX_ROUNDS} rounds")
    stored: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for index, raw in enumerate(rounds):
        round_type = RoundType(raw["type"])
        where = f"rounds.{index}"
        if round_type == RoundType.SYSTEM_DESIGN and difficulty != Difficulty.SENIOR:
            raise PlanError(f"{where}.type", "SENIOR_ONLY", "A system-design round is for senior roles")
        if int(raw["minutes"]) < MIN_ROUND_MINUTES:
            raise PlanError(f"{where}.minutes", "TOO_SHORT", f"A round needs at least {MIN_ROUND_MINUTES} minutes")
        questions = [q.strip() for q in raw.get("questions") or [] if q and q.strip()]
        if not questions:
            raise PlanError(f"{where}.questions", "REQUIRED", "Give at least one core question: every candidate is asked the same ones")
        languages = [lang.strip().lower() for lang in raw.get("languages") or [] if lang and lang.strip()]
        if round_type == RoundType.CODING and not languages:
            raise PlanError(f"{where}.languages", "REQUIRED", "A coding round names the languages a candidate may use")
        criteria = [Criterion(c).value for c in (raw.get("criteria") or [c.value for c in ROUND_DEFAULT_CRITERIA[round_type]])]
        if round_type == RoundType.CODING and Criterion.CODE_QUALITY.value not in criteria:
            raise PlanError(f"{where}.criteria", "REQUIRED", "A coding round is scored on code quality")
        counts[round_type.value] = counts.get(round_type.value, 0) + 1
        stored.append(
            {"key": f"{round_type.value}_{counts[round_type.value]}", "type": round_type.value, "minutes": int(raw["minutes"]), "questions": questions, "languages": languages, "criteria": list(dict.fromkeys(criteria))}
        )
    if sum(r["minutes"] for r in stored) > duration_minutes:
        raise PlanError("rounds", "TOO_LONG", "The rounds add up to more than the interview's duration")
    used = list(dict.fromkeys(c for r in stored for c in r["criteria"]))
    if criteria_weights:
        unknown = set(criteria_weights) - set(used)
        if unknown:
            raise PlanError("criteria_weights", "UNKNOWN_CRITERION", f"No round is scored on: {', '.join(sorted(unknown))}")
        missing = set(used) - set(criteria_weights)
        if missing:
            raise PlanError("criteria_weights", "MISSING_CRITERION", f"Give a weight for: {', '.join(sorted(missing))}")
        total = sum(criteria_weights.values())
        if any(w <= 0 for w in criteria_weights.values()) or abs(total - 1.0) > 0.01:
            raise PlanError("criteria_weights", "INVALID_WEIGHTS", "Weights are positive and add up to 1")
        weights = {c: round(criteria_weights[c] / total, 4) for c in used}
    else:
        weights = {c: round(1 / len(used), 4) for c in used}
    _ = kind
    return stored, weights


def round_seconds(plan_round: dict[str, Any]) -> int:
    return int(plan_round["minutes"]) * 60


def total_seconds(rounds: list[dict[str, Any]]) -> int:
    return sum(round_seconds(r) for r in rounds)
