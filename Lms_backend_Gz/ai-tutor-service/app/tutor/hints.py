"""The hint ladder for practice problems (docs/PRODUCT.md §5.5: "hints before solutions").

Level 0 is nothing given yet; each hint request moves up exactly one rung, whatever the student asks for:

  1 a nudge (what to look at)   2 the approach (the idea, no code)   3 pseudocode / a partial skeleton
  4 the full solution — reachable only after three hints have been given

Pure and monotonic, so it can be enforced and tested outside the model: the prompt is *told* the level; it never decides it.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HintDecision:
    level: int  # the rung this answer is allowed to reach
    solution_allowed: bool
    ladder_finished: bool  # the student is already at the top; the next request repeats it


def next_level(current: int, *, max_level: int) -> HintDecision:
    level = min(current + 1, max_level)
    return HintDecision(level=level, solution_allowed=level >= max_level, ladder_finished=current >= max_level)


LEVEL_NAMES = {
    1: "nudge: point at what to look at, without saying how to fix it",
    2: "approach: explain the idea or algorithm in words, with no code",
    3: "skeleton: pseudocode or a partial outline with the key step left for the student",
    4: "solution: a complete worked solution with an explanation",
}


def describe(level: int) -> str:
    return LEVEL_NAMES.get(level, LEVEL_NAMES[max(LEVEL_NAMES)])
