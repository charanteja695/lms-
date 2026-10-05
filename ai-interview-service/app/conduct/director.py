"""The director decides what happens next in an interview. The model proposes (a follow-up, or "move on"); this code disposes.

What is fixed, whatever a model says (docs/PRODUCT.md §5.8 "Fairness": same plan and rubric for every candidate):
  * the core questions of every round are asked in the plan's order, word for word;
  * a round ends when its time is up, and the interview ends when its time is up — the model cannot extend either;
  * at most ``max_follow_ups`` follow-ups per question, and none when there is too little time left for an answer;
  * the model only ever produces the follow-up's *text*; the director decides whether it is asked.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

MIN_SECONDS_FOR_FOLLOW_UP = 45


class Action(StrEnum):
    FOLLOW_UP = "follow_up"  # ask the model's follow-up on the same question
    NEXT_QUESTION = "next_question"  # the next core question of this round
    NEXT_ROUND = "next_round"  # the first core question of the next round
    WRAP_UP = "wrap_up"  # nothing left: close the interview


@dataclass(frozen=True, slots=True)
class State:
    round_index: int
    question_index: int  # the core question currently being answered (0-based)
    follow_ups: int  # asked on it already
    round_seconds_left: float
    total_seconds_left: float


@dataclass(frozen=True, slots=True)
class Step:
    action: Action
    round_index: int
    question_index: int
    text: str | None  # the question to ask (core question or follow-up); None when wrapping up
    reason: str


def wrap_up_text(plan: dict[str, Any]) -> str:
    return f"That is everything I wanted to cover for the {plan['role']} interview. Thank you for your time — you can end the interview now, and your result will follow."


def opening_text(plan: dict[str, Any]) -> str:
    first = plan["rounds"][0]["questions"][0]
    return f"Hello, and welcome to your {plan['role']} interview. I will ask you a few questions and may follow up on your answers. Take your time. Let us begin. {first}"


def next_step(plan: dict[str, Any], state: State, *, proposed_follow_up: str | None, max_follow_ups: int) -> Step:
    """What to do after the candidate's answer. ``proposed_follow_up`` is the model's follow-up text, if it suggested one."""
    rounds = plan["rounds"]
    if state.total_seconds_left <= 0:
        return Step(Action.WRAP_UP, state.round_index, state.question_index, None, "time_up")
    round_over = state.round_seconds_left <= 0
    if (
        proposed_follow_up
        and proposed_follow_up.strip()
        and not round_over
        and state.follow_ups < max_follow_ups
        and state.round_seconds_left >= MIN_SECONDS_FOR_FOLLOW_UP
        and state.total_seconds_left >= MIN_SECONDS_FOR_FOLLOW_UP
    ):
        return Step(Action.FOLLOW_UP, state.round_index, state.question_index, proposed_follow_up.strip(), "adaptive")
    questions = rounds[state.round_index]["questions"]
    if not round_over and state.question_index + 1 < len(questions):
        return Step(Action.NEXT_QUESTION, state.round_index, state.question_index + 1, questions[state.question_index + 1], "next_core_question")
    if state.round_index + 1 < len(rounds):
        return Step(Action.NEXT_ROUND, state.round_index + 1, 0, rounds[state.round_index + 1]["questions"][0], "round_over" if round_over else "round_done")
    return Step(Action.WRAP_UP, state.round_index, state.question_index, None, "finished")
