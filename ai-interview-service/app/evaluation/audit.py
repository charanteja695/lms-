"""Checks on the AI's fairness and accuracy (docs/PRODUCT.md §5.8 "Fairness": calibration against human-rated samples, periodic bias audits).

Two tools, both pure:
  * ``calibration``: how far the AI's rubric scores are from people's on the same transcripts;
  * ``adverse_impact``: the four-fifths rule on the rate of "advance" recommendations (yes / strong_yes) between groups of candidates. The audit
    groups by the candidate's institution — the one attribute this service holds — and only for groups large enough to mean anything.
"""

from typing import Any

FOUR_FIFTHS = 0.8
ADVANCE = {"yes", "strong_yes"}


def calibration(pairs: list[tuple[dict[str, float], dict[str, float], str, str | None]]) -> dict[str, Any]:
    """``pairs``: (human criterion scores, AI criterion scores, human recommendation, AI recommendation) per sample."""
    diffs: list[float] = []
    agree = 0
    for human, ai, human_rec, ai_rec in pairs:
        diffs += [abs(human[c] - ai[c]) for c in human if c in ai]
        agree += int(human_rec == ai_rec)
    if not pairs or not diffs:
        return {"samples": len(pairs), "mean_abs_error": None, "within_one_rate": None, "recommendation_agreement": None}
    return {
        "samples": len(pairs), "mean_abs_error": round(sum(diffs) / len(diffs), 3), "within_one_rate": round(sum(1 for d in diffs if d <= 1.0) / len(diffs), 3),
        "recommendation_agreement": round(agree / len(pairs), 3),
    }


def adverse_impact(groups: dict[str, tuple[int, int]], *, min_group: int) -> dict[str, Any]:
    """``groups``: label -> (candidates, advanced). Groups under ``min_group`` are listed but not compared (too few to say anything, and a small
    group's numbers could identify a person)."""
    rows: list[dict[str, Any]] = []
    for label, (n, advanced) in sorted(groups.items()):
        rows.append({"group": label, "candidates": n, "advanced": advanced, "advance_rate": round(advanced / n, 3) if n else None, "compared": n >= min_group})
    comparable = [r for r in rows if r["compared"] and r["advance_rate"] is not None]
    best = max((r["advance_rate"] for r in comparable), default=None)
    flagged = []
    for row in comparable:
        ratio = None if not best else round(row["advance_rate"] / best, 3)
        row["impact_ratio"] = ratio
        row["flagged"] = ratio is not None and ratio < FOUR_FIFTHS
        if row["flagged"]:
            flagged.append(row["group"])
    return {"groups": rows, "flagged_groups": flagged, "rule": "four-fifths: a group whose advance rate is under 80% of the best group's is flagged for human review", "min_group": min_group}
