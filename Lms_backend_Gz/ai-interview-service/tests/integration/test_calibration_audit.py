"""Calibration against human-rated samples, and the fairness audit's four-fifths comparison across candidates' institutions (docs/PRODUCT.md §5.8)."""

import json

from tests.conftest import API, EMPLOYER, RECRUITER, create_published_plan, round_body

APPLICATION_A, APPLICATION_B, JOB = 1755000000091001, 1755000000091201, 1755000000091011
STUDENT_A, STUDENT_B = 1755000000092001, 1755000000092201
INST_A, INST_B = 1755000000091101, 1755000000091102


def sample_body(*, score: int = 4, recommendation: str = "yes") -> dict:
    return {
        "turns": [
            {"seq": 1, "round": "technical_1", "speaker": "interviewer", "kind": "question", "text": "Describe a system you built.", "elapsed_ms": 0},
            {"seq": 2, "round": "technical_1", "speaker": "candidate", "kind": "answer", "text": "I built a distributed queue that processed a million jobs a day.", "elapsed_ms": 2000},
        ],
        "human_scores": {"technical_depth": score, "problem_solving": score, "communication": score},
        "human_recommendation": recommendation,
    }


async def test_calibration_needs_scores_for_criteria_the_plan_actually_uses(client, who):
    plan_id = await create_published_plan(client, who, kind="screening", rounds=[round_body(type_="technical", minutes=15)], duration_minutes=15)
    who.recruiter()
    unknown = await client.post(f"{API}/interview-plans/{plan_id}/calibration/samples", json={"turns": sample_body()["turns"], "human_scores": {"behavioural": 4}, "human_recommendation": "yes"})
    assert unknown.status_code == 422 and unknown.json()["details"][0]["code"] == "UNKNOWN_CRITERION"

    out_of_range = await client.post(f"{API}/interview-plans/{plan_id}/calibration/samples", json={"turns": sample_body()["turns"], "human_scores": {"technical_depth": 9}, "human_recommendation": "yes"})
    assert out_of_range.status_code == 422


async def test_a_calibration_run_needs_at_least_one_sample(client, who):
    plan_id = await create_published_plan(client, who, kind="screening", rounds=[round_body(type_="technical", minutes=15)], duration_minutes=15)
    who.recruiter()
    empty = await client.post(f"{API}/interview-plans/{plan_id}/calibration/runs")
    assert empty.status_code == 409 and empty.json()["code"] == "NO_SAMPLES"


async def test_a_calibration_run_compares_the_model_to_the_humans(client, who, gateway):
    plan_id = await create_published_plan(client, who, kind="screening", rounds=[round_body(type_="technical", minutes=15)], duration_minutes=15)
    who.recruiter()
    added = await client.post(f"{API}/interview-plans/{plan_id}/calibration/samples", json=sample_body(score=4, recommendation="yes"))
    assert added.status_code == 201, added.text

    gateway.reply(
        json.dumps(
            {
                "rounds": [{"round": "technical_1", "scores": {c: {"score": 4, "evidence": [{"quote": "I built a distributed queue that processed"}]} for c in ("technical_depth", "problem_solving", "communication")}}],
                "summary": "Matches the human rating.",
            }
        )
    )
    run = await client.post(f"{API}/interview-plans/{plan_id}/calibration/runs")
    assert run.status_code == 201, run.text
    body = run.json()["run"]
    assert body["samples"] == 1 and body["recommendation_agreement"] == 1.0 and body["mean_abs_error"] == 0.0

    listed = await client.get(f"{API}/interview-plans/{plan_id}/calibration/runs")
    assert listed.json()["runs"][0]["run_id"] == body["run_id"]


async def _screened_interview(client, who, send_event, work, gateway, plan_id: str, *, application: int, user: int, org: int, score: int) -> None:
    await send_event(
        "application.stage_changed",
        {"application_id": str(application), "job_id": str(JOB), "employer_id": str(EMPLOYER), "user_id": str(user), "organization_id": str(org), "from": "assessment", "to": "ai_interview_invited", "actor": "system", "interview_plan_id": plan_id},
    )
    await work()
    who.student(user, org)
    interview_id = next(i["interview_id"] for i in (await client.get(f"{API}/student/interviews")).json()["interviews"] if i["plan_id"] == plan_id)
    consent = await client.get(f"{API}/student/interviews/{interview_id}/consent")
    await client.post(f"{API}/student/interviews/{interview_id}/consent", json={"version": consent.json()["consent"]["version"], "recording": True})
    await client.post(f"{API}/student/interviews/{interview_id}/start")
    answer = "I optimised our database queries and cut page load time significantly for every user."
    gateway.reply_follow_up(None)
    await client.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": answer})
    gateway.reply(json.dumps({"rounds": [{"round": "technical_1", "scores": {c: {"score": score, "evidence": [{"quote": answer[:30]}]} for c in ("technical_depth", "problem_solving", "communication")}}], "summary": "Scored."}))
    await work()
    who.recruiter(RECRUITER, EMPLOYER)
    await client.post(f"{API}/employer/interviews/{interview_id}/review", json={})


async def test_the_fairness_audit_flags_a_group_below_four_fifths(client, who, send_event, work, gateway, settings):
    settings_min = settings.AUDIT_MIN_GROUP
    plan_id = await create_published_plan(client, who, kind="screening", rounds=[round_body(type_="technical", minutes=15)], duration_minutes=15)

    for i in range(settings_min):
        await _screened_interview(client, who, send_event, work, gateway, plan_id, application=APPLICATION_A + i, user=STUDENT_A + i, org=INST_A, score=5)  # every candidate from A advances
    for i in range(settings_min):
        await _screened_interview(client, who, send_event, work, gateway, plan_id, application=APPLICATION_B + i, user=STUDENT_B + i, org=INST_B, score=1)  # none from B does

    who.recruiter()
    report = await client.get(f"{API}/interview-plans/{plan_id}/audit")
    assert report.status_code == 200, report.text
    audit = report.json()["audit"]
    assert audit["interviews"] == settings_min * 2 and audit["evaluated"] == settings_min * 2
    groups = {g["group"]: g for g in audit["adverse_impact"]["groups"]}
    assert groups[str(INST_A)]["advance_rate"] == 1.0
    assert groups[str(INST_B)]["advance_rate"] == 0.0
    assert str(INST_B) in audit["adverse_impact"]["flagged_groups"]
    assert audit["override_rate"] == 0.0  # every review confirmed the AI
