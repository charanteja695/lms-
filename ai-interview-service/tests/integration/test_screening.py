"""A hiring interview: the pipeline invites the candidate (``application.stage_changed``), a person must review the AI's recommendation
(never automatic; docs/PRODUCT.md §5.8), an appeal is decided by someone else, and upholding it grants a retake."""

import json

from tests.conftest import API, EMPLOYER, EMPLOYER_2, RECRUITER_2, STUDENT, create_published_plan, round_body

APPLICATION, JOB = 1755000000090001, 1755000000090011


async def _invite(send_event, work, plan_id: str, *, application: int = APPLICATION, employer: int = EMPLOYER, user: int = STUDENT) -> None:
    await send_event(
        "application.stage_changed",
        {"application_id": str(application), "job_id": str(JOB), "employer_id": str(employer), "user_id": str(user), "organization_id": None, "from": "assessment", "to": "ai_interview_invited", "actor": "system", "interview_plan_id": plan_id},
    )
    await work()


async def test_the_pipeline_invites_a_candidate_and_it_is_idempotent(client, who, send_event, work):
    plan_id = await create_published_plan(client, who, kind="screening")
    await _invite(send_event, work, plan_id)

    who.student()
    mine = await client.get(f"{API}/student/interviews")
    assert mine.json()["page_context"]["total_records"] == 1
    interview = mine.json()["interviews"][0]
    assert interview["kind"] == "screening" and interview["status"] == "invited"

    await _invite(send_event, work, plan_id)  # a redelivery of the same stage change
    again = await client.get(f"{API}/student/interviews")
    assert again.json()["page_context"]["total_records"] == 1


async def test_an_ended_application_cancels_an_unstarted_invitation(client, who, send_event, work):
    plan_id = await create_published_plan(client, who, kind="screening")
    await _invite(send_event, work, plan_id)
    await send_event("application.stage_changed", {"application_id": str(APPLICATION), "job_id": str(JOB), "employer_id": str(EMPLOYER), "user_id": str(STUDENT), "from": "ai_interview_invited", "to": "rejected", "actor": "system"})

    who.student()
    mine = await client.get(f"{API}/student/interviews")
    assert mine.json()["interviews"][0]["status"] == "cancelled"


async def _run_screening_interview(client, who, send_event, work, gateway, plan_id: str) -> str:
    await _invite(send_event, work, plan_id)
    who.student()
    interview_id = (await client.get(f"{API}/student/interviews")).json()["interviews"][0]["interview_id"]
    consent = await client.get(f"{API}/student/interviews/{interview_id}/consent")
    await client.post(f"{API}/student/interviews/{interview_id}/consent", json={"version": consent.json()["consent"]["version"], "recording": True})
    await client.post(f"{API}/student/interviews/{interview_id}/start")
    gateway.reply_follow_up(None)
    answer = "I led the migration of our monolith to microservices, cutting deploy time from an hour to five minutes."
    turn = await client.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": answer})
    assert turn.json()["turns"]["finished"] is True
    gateway.reply(json.dumps({"rounds": [{"round": "technical_1", "scores": {"technical_depth": {"score": 5, "evidence": [{"quote": answer[:30]}]}, "problem_solving": {"score": 5, "evidence": [{"quote": answer[:30]}]}, "communication": {"score": 5, "evidence": [{"quote": answer[:30]}]}}}], "summary": "Excellent."}))
    assert await work() == 1
    return str(interview_id)


async def test_a_person_must_review_before_a_candidate_ever_sees_a_hiring_result(client, who, send_event, work, gateway):
    plan_id = await create_published_plan(client, who, kind="screening", rounds=[round_body(type_="technical", minutes=15)], duration_minutes=15)
    interview_id = await _run_screening_interview(client, who, send_event, work, gateway, plan_id)

    who.student()
    unreleased = await client.get(f"{API}/student/interviews/{interview_id}/report")
    assert unreleased.json()["report"]["released"] is False

    who.recruiter()
    detail = await client.get(f"{API}/employer/interviews/{interview_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["interview"]["evaluation"]["recommendation"] == "strong_yes"

    overriding_without_note = await client.post(f"{API}/employer/interviews/{interview_id}/review", json={"recommendation": "no"})
    assert overriding_without_note.status_code == 422

    reviewed = await client.post(f"{API}/employer/interviews/{interview_id}/review", json={"recommendation": "no", "note": "Culture-fit concerns from the recruiter call.", "release_feedback": True})
    assert reviewed.status_code == 200
    assert reviewed.json()["interview"]["final_recommendation"] == "no"

    who.student()
    released = await client.get(f"{API}/student/interviews/{interview_id}/report")
    assert released.json()["report"]["released"] is True
    assert "recommendation" not in released.json()["report"]


async def test_confirming_needs_no_note_and_keeps_the_ai_recommendation(client, who, send_event, work, gateway):
    plan_id = await create_published_plan(client, who, kind="screening", rounds=[round_body(type_="technical", minutes=15)], duration_minutes=15)
    interview_id = await _run_screening_interview(client, who, send_event, work, gateway, plan_id)
    who.recruiter()
    confirmed = await client.post(f"{API}/employer/interviews/{interview_id}/review", json={})
    assert confirmed.status_code == 200
    assert confirmed.json()["interview"]["final_recommendation"] == "strong_yes"


async def test_a_company_cannot_review_another_companys_interview(client, who, send_event, work, gateway):
    plan_id = await create_published_plan(client, who, kind="screening", rounds=[round_body(type_="technical", minutes=15)], duration_minutes=15)
    interview_id = await _run_screening_interview(client, who, send_event, work, gateway, plan_id)
    who.recruiter(RECRUITER_2, EMPLOYER_2)
    hidden = await client.get(f"{API}/employer/interviews/{interview_id}")
    assert hidden.status_code == 404


async def test_appeal_needs_release_and_is_decided_by_a_different_person_then_grants_a_retake(client, who, send_event, work, gateway):
    plan_id = await create_published_plan(client, who, kind="screening", rounds=[round_body(type_="technical", minutes=15)], duration_minutes=15)
    interview_id = await _run_screening_interview(client, who, send_event, work, gateway, plan_id)

    who.student()
    too_early = await client.post(f"{API}/student/interviews/{interview_id}/appeal", json={"reason": "I would like this reconsidered please."})
    assert too_early.status_code == 409 and too_early.json()["code"] == "NOT_RELEASED"

    who.recruiter()
    await client.post(f"{API}/employer/interviews/{interview_id}/review", json={"recommendation": "no", "note": "Did not meet the bar on system design.", "release_feedback": True})

    who.student()
    appealed = await client.post(f"{API}/student/interviews/{interview_id}/appeal", json={"reason": "I believe the transcript was misread."})
    assert appealed.status_code == 201, appealed.text

    who.recruiter()  # the same person who reviewed cannot also decide the appeal
    same_person = await client.post(f"{API}/employer/interviews/{interview_id}/appeal/decide", json={"uphold": True, "note": None})
    assert same_person.status_code == 403 and same_person.json()["code"] == "SECOND_REVIEWER_REQUIRED"

    who.manager()
    open_list = await client.get(f"{API}/employer/appeals")
    assert open_list.json()["page_context"]["total_records"] == 1
    decided = await client.post(f"{API}/employer/interviews/{interview_id}/appeal/decide", json={"uphold": True, "note": "Reviewed the transcript again; giving a retake."})
    assert decided.status_code == 200 and decided.json()["appeal"]["status"] == "upheld"

    who.student()
    retaken = await client.post(f"{API}/student/interviews/{interview_id}/retake")
    assert retaken.status_code == 201
    assert retaken.json()["interview"]["attempt_no"] == 2

    again = await client.post(f"{API}/student/interviews/{interview_id}/retake")
    assert again.status_code == 409 and again.json()["code"] == "RETAKE_EXISTS"


async def test_denying_an_appeal_needs_a_note(client, who, send_event, work, gateway):
    plan_id = await create_published_plan(client, who, kind="screening", rounds=[round_body(type_="technical", minutes=15)], duration_minutes=15)
    interview_id = await _run_screening_interview(client, who, send_event, work, gateway, plan_id)
    who.recruiter()
    await client.post(f"{API}/employer/interviews/{interview_id}/review", json={"release_feedback": True})
    who.student()
    await client.post(f"{API}/student/interviews/{interview_id}/appeal", json={"reason": "Please look at this again."})
    who.manager()
    denied_without_note = await client.post(f"{API}/employer/interviews/{interview_id}/appeal/decide", json={"uphold": False})
    assert denied_without_note.status_code == 422
    denied = await client.post(f"{API}/employer/interviews/{interview_id}/appeal/decide", json={"uphold": False, "note": "The rubric evidence supports the score."})
    assert denied.status_code == 200 and denied.json()["appeal"]["status"] == "denied"


async def test_rerunning_a_failed_evaluation(client, who, send_event, work, gateway, settings):
    settings.WORK_MAX_ATTEMPTS = 1  # so the very first failed attempt gives up, instead of waiting out the backoff
    plan_id = await create_published_plan(client, who, kind="screening", rounds=[round_body(type_="technical", minutes=15)], duration_minutes=15)
    await _invite(send_event, work, plan_id)
    who.student()
    interview_id = (await client.get(f"{API}/student/interviews")).json()["interviews"][0]["interview_id"]
    consent = await client.get(f"{API}/student/interviews/{interview_id}/consent")
    await client.post(f"{API}/student/interviews/{interview_id}/consent", json={"version": consent.json()["consent"]["version"], "recording": True})
    await client.post(f"{API}/student/interviews/{interview_id}/start")
    gateway.completion_error = (500, "DOWN")
    await client.post(f"{API}/student/interviews/{interview_id}/turns", json={"text": "An answer to the only core question."})
    await client.post(f"{API}/student/interviews/{interview_id}/end")

    await work()  # the one allowed attempt fails and the evaluation gives up

    who.recruiter()
    failed = await client.get(f"{API}/employer/interviews/{interview_id}")
    assert failed.json()["interview"]["evaluation"]["status"] == "failed"

    gateway.completion_error = None
    gateway.reply(json.dumps({"rounds": [{"round": "technical_1", "scores": {"technical_depth": {"score": 4, "evidence": [{"quote": "An answer to the only core question."[:20]}]}, "problem_solving": {"score": 4, "evidence": [{"quote": "An answer to the only core question."[:20]}]}, "communication": {"score": 4, "evidence": [{"quote": "An answer to the only core question."[:20]}]}}}], "summary": "Recovered."}))
    rerun = await client.post(f"{API}/employer/interviews/{interview_id}/evaluate")
    assert rerun.status_code == 200
    await work()
    recovered = await client.get(f"{API}/employer/interviews/{interview_id}")
    assert recovered.json()["interview"]["evaluation"]["status"] == "final"
