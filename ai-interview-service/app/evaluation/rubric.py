"""Turning a model's rubric answer into a trustworthy evaluation (docs/PRODUCT.md §5.8 "Evaluation").

The model is asked to score each round on its criteria (1–5) and to back every score with quotes from what the candidate said. Then this code:

  * **verifies every quote** against the transcript — it must appear, word for word (ignoring case and spacing), in a candidate's turn; a quote
    that does not is dropped and counted (a model that invents evidence is visible in ``invalid_quotes``);
  * **clamps a score with no evidence** — a 1, 2, 4 or 5 needs at least ``MIN_EVIDENCE`` verified quotes, otherwise it becomes a 3 and is flagged;
  * scores a coding round's **code quality** as 1 when no code was run, whatever the model said (there was nothing to judge);
  * computes the **overall score and the recommendation itself** from the plan's weights and thresholds. The model never chooses the recommendation.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.domain.enums import Criterion, Recommendation

_SPACE = re.compile(r"\s+")
_EDGE = re.compile(r"^[\W_]+|[\W_]+$")
MIN_QUOTE_CHARS = 12
SCORE_MIN, SCORE_MAX = 1, 5  # every criterion is scored on this scale; the overall score is their weighted mean


def _norm(text: str) -> str:
    return _EDGE.sub("", _SPACE.sub(" ", text.lower()).strip())


@dataclass(slots=True)
class Evaluated:
    rounds: list[dict[str, Any]] = field(default_factory=list)
    criterion_scores: dict[str, float] = field(default_factory=dict)
    overall: float | None = None
    recommendation: str | None = None
    summary: str = ""
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    invalid_quotes: int = 0
    total_quotes: int = 0


def parse(text: str) -> dict[str, Any] | None:
    """The model's JSON answer, or ``None`` when it is not a JSON object with a ``rounds`` list."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) and isinstance(data.get("rounds"), list) else None


def recommend(overall: float, *, strong_yes_at: float, yes_at: float, lean_no_at: float) -> str:
    if overall >= strong_yes_at:
        return Recommendation.STRONG_YES.value
    if overall >= yes_at:
        return Recommendation.YES.value
    if overall >= lean_no_at:
        return Recommendation.LEAN_NO.value
    return Recommendation.NO.value


def _strings(value: Any, limit: int, size: int = 240) -> list[str]:
    return [str(v).strip()[:size] for v in value if isinstance(v, str) and v.strip()][:limit] if isinstance(value, list) else []


def verify(
    data: dict[str, Any], *, plan: dict[str, Any], turns: list[dict[str, Any]], min_evidence: int, thresholds: tuple[float, float, float], integrity_invalidated: bool = False
) -> Evaluated:
    """``turns``: the transcript as ``[{seq, speaker, kind, round, text, elapsed_ms}]``. ``thresholds``: (strong_yes_at, yes_at, lean_no_at)."""
    result = Evaluated()
    candidate_turns = {t["seq"]: t for t in turns if t["speaker"] == "candidate" and t["kind"] == "answer"}
    normalised = {seq: _norm(t["text"]) for seq, t in candidate_turns.items()}
    ran_code = {t["round"] for t in turns if t["kind"] == "code"}
    plan_rounds = {r["key"]: r for r in plan["rounds"]}
    by_round = {str(item.get("round")): item for item in data.get("rounds", []) if isinstance(item, dict)}
    sums: dict[str, list[float]] = {}
    for key, plan_round in plan_rounds.items():
        raw = by_round.get(key)
        scored: dict[str, Any] = {}
        for criterion in plan_round["criteria"]:
            entry = (raw or {}).get("scores", {}).get(criterion) if isinstance((raw or {}).get("scores"), dict) else None
            if not isinstance(entry, dict) or isinstance(entry.get("score"), bool) or not isinstance(entry.get("score"), int | float):
                result.flags.append(f"{key}: no score for {criterion}; left out")
                continue
            score = min(5, max(1, round(float(entry["score"]))))
            evidence: list[dict[str, Any]] = []
            for item in entry.get("evidence", []) if isinstance(entry.get("evidence"), list) else []:
                if not isinstance(item, dict) or not isinstance(item.get("quote"), str):
                    continue
                quote = _norm(item["quote"])
                result.total_quotes += 1
                if len(quote) < MIN_QUOTE_CHARS:
                    result.invalid_quotes += 1
                    continue
                hint = item.get("turn")
                seq = next((s for s in ([hint] if hint in normalised else []) + list(normalised) if quote in normalised[s]), None)
                if seq is None:
                    result.invalid_quotes += 1
                    continue
                turn = candidate_turns[seq]
                evidence.append({"quote": item["quote"].strip()[:400], "turn": seq, "elapsed_ms": turn["elapsed_ms"], "round": turn["round"]})
            if criterion == Criterion.CODE_QUALITY.value and plan_round["type"] == "coding" and key not in ran_code:
                score, evidence = 1, []
                result.flags.append(f"{key}: no code was run, so code quality is scored 1")
            elif score in (1, 2, 4, 5) and len(evidence) < min_evidence:
                result.flags.append(f"{key}: {criterion} was scored {score} without verified evidence; scored 3 instead")
                score = 3
            scored[criterion] = {"score": score, "evidence": evidence}
            sums.setdefault(criterion, []).append(float(score))
        result.rounds.append({"round": key, "type": plan_round["type"], "scores": scored, "comment": str((raw or {}).get("comment") or "")[:500]})
    if result.invalid_quotes:
        result.flags.append(f"{result.invalid_quotes} of {result.total_quotes} quotes could not be found in the transcript and were dropped")
    result.criterion_scores = {c: round(sum(v) / len(v), 2) for c, v in sums.items()}
    weights = {c: w for c, w in plan["criteria_weights"].items() if c in result.criterion_scores}
    if weights:
        total = sum(weights.values())
        result.overall = round(sum(result.criterion_scores[c] * w for c, w in weights.items()) / total, 2)
        result.recommendation = recommend(result.overall, strong_yes_at=thresholds[0], yes_at=thresholds[1], lean_no_at=thresholds[2])
        if integrity_invalidated and result.recommendation in (Recommendation.STRONG_YES.value, Recommendation.YES.value):
            result.recommendation = Recommendation.LEAN_NO.value
            result.flags.append("the integrity decision invalidated this interview: the recommendation is capped at lean_no")
    result.summary = str(data.get("summary") or "")[:1200]
    result.strengths = _strings(data.get("strengths"), 5)
    result.improvements = _strings(data.get("improvements"), 5)
    return result
