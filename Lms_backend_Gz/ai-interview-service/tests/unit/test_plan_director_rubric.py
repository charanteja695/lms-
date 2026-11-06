import json

import pytest

from app.conduct import director
from app.conduct.director import Action, State
from app.conduct.plan_rules import PlanError, normalise
from app.domain.enums import Difficulty, PlanKind
from app.evaluation import audit, rubric

ROUNDS = [
    {"type": "intro", "minutes": 3, "questions": ["Tell me about yourself."]},
    {"type": "technical", "minutes": 10, "questions": ["What is a database index?", "Explain ACID."]},
    {"type": "coding", "minutes": 15, "questions": ["Write a function that reverses a string."], "languages": ["python3"]},
    {"type": "behavioural", "minutes": 5, "questions": ["Describe a disagreement with a teammate."]},
]


def build(**overrides):
    args = {"kind": PlanKind.SCREENING, "difficulty": Difficulty.MEDIUM, "duration_minutes": 40, "rounds": ROUNDS, "criteria_weights": None}
    args.update(overrides)
    return normalise(**args)


def plan_dict(rounds=None, weights=None):
    stored, default_weights = build()
    return {"role": "Backend Developer", "rounds": rounds or stored, "criteria_weights": weights or default_weights}


# ---------------------------------------------------------------- plan rules
def test_a_valid_plan_gets_round_keys_default_criteria_and_equal_weights():
    rounds, weights = build()
    assert [r["key"] for r in rounds] == ["intro_1", "technical_1", "coding_1", "behavioural_1"]
    assert rounds[2]["criteria"] == ["problem_solving", "code_quality", "technical_depth"] and rounds[2]["languages"] == ["python3"]
    assert set(weights) == {"communication", "technical_depth", "problem_solving", "code_quality", "behavioural"} and sum(weights.values()) == pytest.approx(1.0, abs=0.001)


def test_two_rounds_of_one_type_are_numbered():
    rounds, _ = build(rounds=[ROUNDS[1], ROUNDS[1]], duration_minutes=30)
    assert [r["key"] for r in rounds] == ["technical_1", "technical_2"]


@pytest.mark.parametrize(
    ("overrides", "field", "code"),
    [
        ({"duration_minutes": 5}, "duration_minutes", "OUT_OF_RANGE"), ({"duration_minutes": 20}, "rounds", "TOO_LONG"), ({"rounds": []}, "rounds", "OUT_OF_RANGE"),
        ({"rounds": [{"type": "technical", "minutes": 1, "questions": ["q"]}]}, "rounds.0.minutes", "TOO_SHORT"),
        ({"rounds": [{"type": "technical", "minutes": 5, "questions": []}]}, "rounds.0.questions", "REQUIRED"),
        ({"rounds": [{"type": "coding", "minutes": 10, "questions": ["q"]}]}, "rounds.0.languages", "REQUIRED"),
        ({"rounds": [{"type": "system_design", "minutes": 10, "questions": ["q"]}]}, "rounds.0.type", "SENIOR_ONLY"),
        ({"rounds": [{"type": "coding", "minutes": 10, "questions": ["q"], "languages": ["python3"], "criteria": ["problem_solving"]}]}, "rounds.0.criteria", "REQUIRED"),
        ({"criteria_weights": {"communication": 1.0}}, "criteria_weights", "MISSING_CRITERION"),
        ({"criteria_weights": {"communication": 0.5, "technical_depth": 0.5, "problem_solving": 0.5, "code_quality": 0.5, "behavioural": 0.5}}, "criteria_weights", "INVALID_WEIGHTS"),
    ],
)
def test_invalid_plans_say_what_is_wrong(overrides, field, code):
    with pytest.raises(PlanError) as caught:
        build(**overrides)
    assert (caught.value.field, caught.value.code) == (field, code)


def test_a_senior_plan_may_have_a_system_design_round_and_custom_weights_are_kept():
    rounds, weights = build(difficulty=Difficulty.SENIOR, rounds=[{"type": "system_design", "minutes": 20, "questions": ["Design a URL shortener."]}], duration_minutes=30, criteria_weights={"technical_depth": 0.5, "problem_solving": 0.25, "communication": 0.25})
    assert rounds[0]["key"] == "system_design_1" and weights == {"technical_depth": 0.5, "problem_solving": 0.25, "communication": 0.25}


# ---------------------------------------------------------------- the director
PLAN = {"role": "Backend Developer", "rounds": [{"questions": ["A1", "A2"]}, {"questions": ["B1"]}]}


def step(*, round_index=0, question=0, follow_ups=0, round_left=300, total_left=1000, follow="Why?", max_follow_ups=2):
    return director.next_step(PLAN, State(round_index, question, follow_ups, round_left, total_left), proposed_follow_up=follow, max_follow_ups=max_follow_ups)


def test_the_opening_is_the_first_core_question_verbatim():
    assert director.opening_text(PLAN).endswith("A1") and "Backend Developer interview" in director.opening_text(PLAN)


def test_a_follow_up_is_asked_when_there_is_time_and_the_limit_allows():
    result = step()
    assert (result.action, result.text, result.question_index) == (Action.FOLLOW_UP, "Why?", 0)


def test_the_limit_time_and_the_lack_of_a_proposal_all_move_the_interview_on():
    assert step(follow_ups=2).action == Action.NEXT_QUESTION and step(follow_ups=2).text == "A2"
    assert step(round_left=30).action == Action.NEXT_QUESTION  # too little time for an answer
    assert step(follow=None).action == Action.NEXT_QUESTION and step(follow="  ").text == "A2"  # a blank proposal is no proposal


def test_core_questions_are_asked_in_order_then_the_next_round_then_the_end():
    second = step(question=1, follow=None)
    assert (second.action, second.round_index, second.text) == (Action.NEXT_ROUND, 1, "B1")
    last = step(round_index=1, question=0, follow=None)
    assert last.action == Action.WRAP_UP and last.text is None and last.reason == "finished"


def test_time_is_decided_by_the_clock_not_the_model():
    assert step(round_left=0).action == Action.NEXT_ROUND and step(round_left=0).reason == "round_over"  # a round's time is up: on to the next
    assert step(round_index=1, round_left=0, follow=None).action == Action.WRAP_UP
    assert step(total_left=0).action == Action.WRAP_UP and step(total_left=0).reason == "time_up"
    assert step(total_left=20).action == Action.NEXT_QUESTION  # no time to follow up, and the next question is still asked
    assert "Thank you" in director.wrap_up_text(PLAN)


# ---------------------------------------------------------------- the rubric
def transcript():
    return [
        {"seq": 1, "speaker": "interviewer", "kind": "question", "round": "technical_1", "text": "What is an index?", "elapsed_ms": 1000},
        {"seq": 2, "speaker": "candidate", "kind": "answer", "round": "technical_1", "text": "An index is a sorted structure that lets the database find rows without scanning the whole table.", "elapsed_ms": 30_000},
        {"seq": 3, "speaker": "candidate", "kind": "answer", "round": "coding_1", "text": "I would reverse it using slicing, which runs in linear time.", "elapsed_ms": 90_000},
        {"seq": 4, "speaker": "candidate", "kind": "code", "round": "coding_1", "text": "def rev(s): return s[::-1]", "elapsed_ms": 95_000},
    ]


PLAN2 = {
    "rounds": [
        {"key": "technical_1", "type": "technical", "criteria": ["technical_depth", "communication"]},
        {"key": "coding_1", "type": "coding", "criteria": ["problem_solving", "code_quality"]},
    ],
    "criteria_weights": {"technical_depth": 0.3, "communication": 0.2, "problem_solving": 0.25, "code_quality": 0.25},
}
THRESHOLDS = (4.2, 3.4, 2.6)


def answer(**overrides):
    body = {
        "rounds": [
            {"round": "technical_1", "scores": {
                "technical_depth": {"score": 5, "evidence": [{"quote": "a sorted structure that lets the database find rows", "turn": 2}]},
                "communication": {"score": 4, "evidence": [{"quote": "without scanning the whole table", "turn": 2}]}}, "comment": "Clear."},
            {"round": "coding_1", "scores": {
                "problem_solving": {"score": 4, "evidence": [{"quote": "reverse it using slicing, which runs in linear time", "turn": 3}]},
                "code_quality": {"score": 4, "evidence": [{"quote": "reverse it using slicing", "turn": 3}]}}, "comment": ""},
        ],
        "summary": "A solid candidate.", "strengths": ["Knows indexes"], "improvements": ["Discuss edge cases"],
    }
    body.update(overrides)
    return body


def check(data, **kw):
    return rubric.verify(data, plan=PLAN2, turns=transcript(), min_evidence=1, thresholds=THRESHOLDS, **kw)


def test_parse_accepts_only_a_json_object_with_rounds():
    assert rubric.parse('Here you go: {"rounds": []} thanks') == {"rounds": []}
    assert rubric.parse("no json") is None and rubric.parse('{"rounds": 3}') is None and rubric.parse("{not json}") is None


def test_verified_evidence_is_kept_with_its_moment_and_the_recommendation_is_computed():
    result = check(answer())
    scored = result.rounds[0]["scores"]["technical_depth"]
    assert scored["score"] == 5 and scored["evidence"][0]["turn"] == 2 and scored["evidence"][0]["elapsed_ms"] == 30_000
    assert result.invalid_quotes == 0 and result.total_quotes == 4 and result.flags == []
    # a code turn is the candidate's work, not their words: quotes are only taken from what they said
    expected = (5 * 0.3 + 4 * 0.2 + 4 * 0.25 + 4 * 0.25) / 1.0
    assert result.overall == pytest.approx(round(expected, 2)) and result.recommendation == "strong_yes" and result.summary == "A solid candidate."


def test_an_invented_quote_is_dropped_and_its_score_loses_its_backing():
    data = answer()
    data["rounds"][0]["scores"]["technical_depth"]["evidence"] = [{"quote": "I have ten years of experience tuning Postgres", "turn": 2}]
    result = check(data)
    scored = result.rounds[0]["scores"]["technical_depth"]
    assert scored["evidence"] == [] and scored["score"] == 3  # a 5 with no verified evidence becomes a 3
    assert result.invalid_quotes == 1 and any("technical_depth was scored 5 without verified evidence" in f for f in result.flags)
    assert any("1 of 4 quotes could not be found" in f for f in result.flags)


def test_a_quote_on_the_wrong_turn_is_found_on_the_right_one_and_case_and_spacing_do_not_matter():
    data = answer()
    data["rounds"][0]["scores"]["communication"]["evidence"] = [{"quote": "WITHOUT   scanning the whole table.", "turn": 3}]
    result = check(data)
    assert result.rounds[0]["scores"]["communication"]["evidence"][0]["turn"] == 2 and result.invalid_quotes == 0


def test_a_very_short_quote_is_not_evidence_and_a_middling_score_needs_none():
    data = answer()
    data["rounds"][0]["scores"]["communication"] = {"score": 3, "evidence": [{"quote": "index", "turn": 2}]}
    result = check(data)
    assert result.rounds[0]["scores"]["communication"]["score"] == 3 and result.invalid_quotes == 1


def test_no_code_run_means_code_quality_is_scored_one():
    turns = [t for t in transcript() if t["kind"] != "code"]
    result = rubric.verify(answer(), plan=PLAN2, turns=turns, min_evidence=1, thresholds=THRESHOLDS)
    assert result.rounds[1]["scores"]["code_quality"] == {"score": 1, "evidence": []} and any("no code was run" in f for f in result.flags)
    assert result.overall < 4.2 and result.recommendation != "strong_yes"


def test_missing_scores_are_left_out_and_weights_renormalised():
    data = answer()
    del data["rounds"][1]["scores"]["problem_solving"]
    result = check(data)
    assert "problem_solving" not in result.criterion_scores and any("no score for problem_solving" in f for f in result.flags) and result.overall is not None
    nothing = check({"rounds": []})
    assert nothing.overall is None and nothing.recommendation is None and len(nothing.flags) == 4


def test_the_score_is_clamped_and_an_invalidated_integrity_decision_caps_the_recommendation():
    data = answer()
    data["rounds"][0]["scores"]["technical_depth"]["score"] = 9
    assert check(data).rounds[0]["scores"]["technical_depth"]["score"] == 5
    capped = check(answer(), integrity_invalidated=True)
    assert capped.recommendation == "lean_no" and any("integrity" in f for f in capped.flags)


@pytest.mark.parametrize(("overall", "expected"), [(4.5, "strong_yes"), (4.2, "strong_yes"), (3.8, "yes"), (3.4, "yes"), (3.0, "lean_no"), (2.6, "lean_no"), (2.0, "no")])
def test_recommendation_thresholds(overall, expected):
    assert rubric.recommend(overall, strong_yes_at=4.2, yes_at=3.4, lean_no_at=2.6) == expected


# ---------------------------------------------------------------- audits
def test_calibration_measures_distance_from_the_humans():
    metrics = audit.calibration([({"a": 4, "b": 3}, {"a": 4, "b": 5}, "yes", "yes"), ({"a": 2, "b": 2}, {"a": 3, "b": 2}, "lean_no", "yes")])
    assert metrics == {"samples": 2, "mean_abs_error": 0.75, "within_one_rate": 0.75, "recommendation_agreement": 0.5}
    assert audit.calibration([])["mean_abs_error"] is None


def test_adverse_impact_flags_a_group_under_four_fifths_and_ignores_tiny_groups():
    report = audit.adverse_impact({"college_a": (40, 20), "college_b": (30, 9), "college_c": (5, 0)}, min_group=10)
    rows = {r["group"]: r for r in report["groups"]}
    assert rows["college_a"]["impact_ratio"] == 1.0 and rows["college_b"]["impact_ratio"] == 0.6 and rows["college_b"]["flagged"] is True and report["flagged_groups"] == ["college_b"]
    assert rows["college_c"]["compared"] is False and "impact_ratio" not in rows["college_c"]
    assert audit.adverse_impact({"x": (3, 1)}, min_group=10)["flagged_groups"] == []
    assert json.dumps(report)
