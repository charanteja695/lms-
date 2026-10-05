import json
from datetime import timedelta

from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.application import Application, ApplicationStage, RejectionBatch
from app.models.offer import Offer
from app.models.outbox_event import OutboxEvent
from app.worker.runner import sweep_once
from tests.conftest import API, FULL_PIPELINE, PLAN_ID, STUDENT, STUDENT_3, STUDENT_4, TEST_ID, apply, hiring_world


async def events(sessionmaker, kind: str) -> list[dict]:
    async with sessionmaker() as db:
        return [r.payload for r in (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == kind).order_by(OutboxEvent.created_at))).scalars()]


async def status_of(client, who, application_id: str, user: int = STUDENT) -> str:
    who.student(user)
    return (await client.get(f"{API}/applications/{application_id}")).json()["application"]["status"]


def finalized(attempt: int, *, user: int = STUDENT, percent: float = 82.0, result: str = "passed", revision: int = 1, integrity: str | None = "clear", test: int = TEST_ID) -> dict:
    return {"attempt_id": str(attempt), "test_id": str(test), "test_kind": "hiring", "user_id": str(user), "result": result, "percent": percent, "integrity_status": integrity, "revision": revision}


# ---------------------------------------------------------------- shortlisting and rejecting: a person, a confirmation
async def test_shortlisting_by_ids_and_by_threshold(client, who, send_event, work, career):
    job_id = await hiring_world(client, who, send_event, work, students=(STUDENT, STUDENT_3, STUDENT_4))
    a1 = await apply(client, who, job_id, career=career)
    a3 = await apply(client, who, job_id, user=STUDENT_3, career=career)
    await apply(client, who, job_id, user=STUDENT_4, career=career)
    await work()
    who.recruiter()
    both = {"application_ids": [a1["application_id"]], "threshold": 10}
    assert (await client.post(f"{API}/employer/jobs/{job_id}/applications/shortlist", json=both)).status_code == 422
    assert (await client.post(f"{API}/employer/jobs/{job_id}/applications/shortlist", json={})).status_code == 422
    done = (await client.post(f"{API}/employer/jobs/{job_id}/applications/shortlist", json={"application_ids": [a1["application_id"]]})).json()
    assert done["count"] == 1 and done["application_ids"] == [a1["application_id"]]
    assert (await client.post(f"{API}/employer/jobs/{job_id}/applications/shortlist", json={"application_ids": [a1["application_id"]]})).status_code == 409  # already shortlisted
    by_threshold = (await client.post(f"{API}/employer/jobs/{job_id}/applications/shortlist", json={"threshold": 0})).json()
    assert by_threshold["count"] == 2 and a3["application_id"] in by_threshold["application_ids"]
    assert (await client.post(f"{API}/employer/jobs/{job_id}/applications/shortlist", json={"threshold": 0})).json()["count"] == 0  # nobody left undecided
    assert (await client.post(f"{API}/employer/jobs/{job_id}/applications/shortlist", json={"application_ids": ["1755000000079999"]})).status_code == 404
    assert await status_of(client, who, a1["application_id"]) == "shortlisted"


async def test_rejection_needs_a_persons_confirmation_and_is_recorded_as_a_batch(client, who, send_event, work, career, sessionmaker):
    job_id = await hiring_world(client, who, send_event, work, students=(STUDENT, STUDENT_3, STUDENT_4))
    ids = [(await apply(client, who, job_id, user=u, career=career))["application_id"] for u in (STUDENT, STUDENT_3, STUDENT_4)]
    await work()
    who.recruiter()
    body = {"application_ids": ids[1:], "reason": "Not enough experience for this role", "threshold": 45}
    unconfirmed = await client.post(f"{API}/employer/jobs/{job_id}/applications/reject", json={**body, "confirm": False})
    assert unconfirmed.status_code == 422 and unconfirmed.json()["details"][0]["code"] == "CONFIRMATION_REQUIRED"
    assert (await client.post(f"{API}/employer/jobs/{job_id}/applications/reject", json=body)).status_code == 422  # confirm is not optional
    done = await client.post(f"{API}/employer/jobs/{job_id}/applications/reject", json={**body, "confirm": True})
    assert done.status_code == 201
    batch = done.json()["batch"]
    assert batch["application_ids"] == ids[1:] and batch["reason"] == body["reason"] and batch["threshold"] == 45
    assert batch["recommended_count"] + batch["not_recommended_count"] == 2
    for application_id, user in zip(ids[1:], (STUDENT_3, STUDENT_4), strict=True):
        assert await status_of(client, who, application_id, user) == "rejected"
    assert await status_of(client, who, ids[0]) == "ai_screened"
    async with sessionmaker() as db:
        stages = (await db.execute(select(ApplicationStage).where(ApplicationStage.to_status == "rejected"))).scalars().all()
        stored = (await db.execute(select(RejectionBatch))).scalar_one()
    assert {s.batch_id for s in stages} == {stored.public_id} and {s.actor for s in stages} == {"recruiter"} and stored.confirmed_by == 1755000000070111 and len(stored.application_ids) == 2
    who.recruiter()
    again = await client.post(f"{API}/employer/jobs/{job_id}/applications/reject", json={**body, "confirm": True})
    assert again.status_code == 409 and again.json()["code"] == "APPLICATION_CLOSED"
    assert (await client.post(f"{API}/employer/jobs/{job_id}/applications/reject", json={"application_ids": ["1755000000079999"], "reason": "x", "confirm": True})).status_code == 404
    rejected = (await client.get(f"{API}/employer/applications/{ids[1]}")).json()["application"]
    assert rejected["decision_reason"] == body["reason"] and rejected["history"][-1]["to_status"] == "rejected"
    assert len(await events(sessionmaker, "application.stage_changed")) >= 5


async def test_the_ai_recommended_rejections_are_counted_in_the_batch(client, who, send_event, work, career, gateway):
    from tests.conftest import COURSE_PY, ORG_A, profile_event

    job_id = await hiring_world(client, who, send_event, work, students=(STUDENT,))
    await profile_event(send_event, STUDENT_4, ORG_A, skills=("HTML",), technologies=(), certificates=(COURSE_PY,), scores=((COURSE_PY, 50.0),), roles=(), titles=(), months=0)
    await work()
    gateway.reply(json.dumps({"score": 85, "reasons": ["good"], "red_flags": []}))
    good = await apply(client, who, job_id, career=career)
    await work()
    gateway.reply(json.dumps({"score": 5, "reasons": ["poor"], "red_flags": []}))
    poor = await apply(client, who, job_id, user=STUDENT_4, career=career)
    await work()
    who.recruiter()
    batch = (await client.post(f"{API}/employer/jobs/{job_id}/applications/reject", json={"application_ids": [poor["application_id"], good["application_id"]], "reason": "Role filled", "confirm": True})).json()["batch"]
    assert (batch["recommended_count"], batch["not_recommended_count"]) == (1, 1)  # a person may reject someone the AI liked; it is on the record


# ---------------------------------------------------------------- the stages
async def test_a_plain_pipeline_goes_from_shortlist_to_review_and_offer(client, who, send_event, work, career):
    job_id = await hiring_world(client, who, send_event, work)
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    await work()
    who.recruiter()
    illegal = await client.post(f"{API}/employer/applications/{aid}/transition", json={"to": "recruiter_review"})
    assert illegal.status_code == 409 and illegal.json()["code"] == "INVALID_TRANSITION"  # not shortlisted yet
    for target in ("offered", "placed", "rejected", "offer_accepted", "withdrawn"):
        assert (await client.post(f"{API}/employer/applications/{aid}/transition", json={"to": target})).status_code in (409, 422), target
    assert (await client.post(f"{API}/employer/applications/{aid}/transition", json={"to": "offered"})).json()["code"] == "USE_DEDICATED_STEP"
    moved = (await client.post(f"{API}/employer/applications/{aid}/advance")).json()["application"]
    assert moved["status"] == "shortlisted"
    assert (await client.post(f"{API}/employer/applications/{aid}/transition", json={"to": "assessment_invited"})).json()["code"] == "INVALID_TRANSITION"  # this job has no assessment
    assert (await client.post(f"{API}/employer/applications/{aid}/advance")).json()["application"]["status"] == "recruiter_review"
    assert (await client.post(f"{API}/employer/applications/{aid}/advance")).json()["code"] == "NO_DEFAULT_STEP"  # the next step is an offer: a decision with terms


async def test_the_full_pipeline_with_assessment_interview_and_hr_round(client, who, send_event, work, career, assessment, sessionmaker):
    job_id = await hiring_world(client, who, send_event, work, pipeline=FULL_PIPELINE)
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    await work()
    who.recruiter()
    await client.post(f"{API}/employer/applications/{aid}/advance")  # shortlisted
    assert (await client.post(f"{API}/employer/applications/{aid}/transition", json={"to": "recruiter_review"})).status_code == 409  # the assessment cannot be skipped
    invited = (await client.post(f"{API}/employer/applications/{aid}/advance")).json()["application"]
    assert invited["status"] == "assessment_invited" and invited["assessment"] == {"test_id": str(TEST_ID), "invite_state": "pending", "percent": None, "result": None, "integrity": None}
    await work()
    assert len(assessment.invites) == 1 and assessment.invites[0]["test_id"] == str(TEST_ID) and assessment.invites[0]["user_id"] == str(STUDENT) and assessment.invites[0]["reference"] == aid
    assert (await client.get(f"{API}/employer/applications/{aid}")).json()["application"]["assessment"]["invite_state"] == "sent"
    assert (await client.post(f"{API}/employer/applications/{aid}/transition", json={"to": "assessment_completed"})).json()["code"] == "USE_DEDICATED_STEP"  # recorded by the platform, not named by a recruiter
    await send_event("attempt.finalized", finalized(9001, test=TEST_ID + 1))  # another test: not this application's
    assert (await client.get(f"{API}/employer/applications/{aid}")).json()["application"]["status"] == "assessment_invited"
    await send_event("attempt.finalized", finalized(9002))
    done = (await client.get(f"{API}/employer/applications/{aid}")).json()["application"]
    assert done["status"] == "assessment_completed" and done["assessment"]["percent"] == 82.0 and done["assessment"]["result"] == "passed" and done["assessment"]["integrity"] == "clear"
    assert done["history"][-1]["actor"] == "system" and done["history"][-1]["note"] == "Assessment passed (82%)"
    interview = (await client.post(f"{API}/employer/applications/{aid}/advance")).json()["application"]
    assert interview["status"] == "ai_interview_invited"
    stage = [e for e in await events(sessionmaker, "application.stage_changed") if e["to"] == "ai_interview_invited"]
    assert stage[0]["interview_plan_id"] == str(PLAN_ID)  # the AI interviewer service reads this to start the interview
    await send_event("interview.completed", {"application_id": aid, "interview_id": "1755000000074001", "recommendation": "yes", "score": 7.5, "report": {"summary": "Clear thinker"}})
    after = (await client.get(f"{API}/employer/applications/{aid}")).json()["application"]
    assert after["status"] == "ai_interview_completed" and after["interview"] == {"recommendation": "yes", "score": 7.5, "report": {"summary": "Clear thinker"}}
    assert (await client.post(f"{API}/employer/applications/{aid}/advance")).json()["application"]["status"] == "recruiter_review"
    assert (await client.post(f"{API}/employer/applications/{aid}/offer", json={"ctc": 900_000})).status_code == 409  # the HR round is required by this job
    when = (utcnow() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    hr = (await client.post(f"{API}/employer/applications/{aid}/transition", json={"to": "hr_interview", "hr_interview_at": when, "note": "Bring your documents"})).json()["application"]
    assert hr["status"] == "hr_interview" and hr["hr_interview_at"] == when
    assert (await client.post(f"{API}/employer/applications/{aid}/offer", json={"ctc": 900_000})).status_code == 201


async def test_a_completion_event_for_the_wrong_moment_changes_nothing(client, who, send_event, work, career):
    job_id = await hiring_world(client, who, send_event, work, pipeline=FULL_PIPELINE)
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    await work()
    await send_event("attempt.finalized", finalized(9100))  # before they were ever invited
    await send_event("interview.completed", {"application_id": aid, "recommendation": "yes"})
    await send_event("interview.completed", {"application_id": "1755000000079999", "recommendation": "yes"})
    await send_event("interview.completed", {"recommendation": "yes"})
    assert await status_of(client, who, aid) == "ai_screened"
    await send_event("attempt.finalized", {**finalized(9101), "test_kind": "practice"})  # only hiring tests count
    assert await status_of(client, who, aid) == "ai_screened"


async def test_a_revised_assessment_result_is_shown_to_the_recruiter_but_decides_nothing(client, who, send_event, work, career, assessment, sessionmaker):
    job_id = await hiring_world(client, who, send_event, work, pipeline={"assessment": {"test_id": str(TEST_ID), "min_percent": 60}})
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    await work()
    who.recruiter()
    await client.post(f"{API}/employer/applications/{aid}/advance")
    await client.post(f"{API}/employer/applications/{aid}/advance")
    await work()
    await send_event("attempt.finalized", finalized(9200, percent=88.0))
    await client.post(f"{API}/employer/applications/{aid}/advance")  # on to recruiter review
    await send_event("attempt.finalized", finalized(9200, percent=88.0, result="invalidated", integrity="invalidated", revision=2))  # an integrity ruling
    await send_event("attempt.finalized", finalized(9200, percent=88.0, revision=1))  # an older release arriving late
    row = (await client.get(f"{API}/employer/applications/{aid}")).json()["application"]
    assert row["status"] == "recruiter_review"  # not moved backwards, not rejected
    assert row["assessment"]["result"] == "invalidated" and row["assessment"]["integrity"] == "invalidated"
    assert any((h["note"] or "").startswith("Assessment result revised: invalidated") for h in row["history"])
    assert len(await events(sessionmaker, "application.assessment_revised")) == 1


async def test_assessment_invitation_failures(client, who, send_event, work, career, assessment, sessionmaker):
    job_id = await hiring_world(client, who, send_event, work, students=(STUDENT, STUDENT_3), pipeline={"assessment": {"test_id": str(TEST_ID)}})
    first = await apply(client, who, job_id, career=career)
    second = await apply(client, who, job_id, user=STUDENT_3, career=career)
    await work()
    who.recruiter()
    for application in (first, second):
        await client.post(f"{API}/employer/applications/{application['application_id']}/advance")
        await client.post(f"{API}/employer/applications/{application['application_id']}/advance")
    assessment.status, assessment.code = 503, "DOWN"  # assessment-service is down: the work is retried, the application waits
    await work(limit=1)
    row = (await client.get(f"{API}/employer/applications/{first['application_id']}")).json()["application"]
    assert row["status"] == "assessment_invited" and row["assessment"]["invite_state"] == "pending"
    async with sessionmaker() as db:
        await db.execute(__import__("sqlalchemy").text("UPDATE work_items SET run_after = '2000-01-01 00:00:00'"))
        await db.commit()
    assessment.status, assessment.code = 409, "TEST_NOT_PUBLISHED"  # a refusal that can never succeed
    await work()
    for application in (first, second):
        row = (await client.get(f"{API}/employer/applications/{application['application_id']}")).json()["application"]
        assert row["assessment"]["invite_state"] == "failed" and any("Assessment invitation refused (TEST_NOT_PUBLISHED)" in (h["note"] or "") for h in row["history"])
    assessment.status = 201
    assert len(assessment.invites) >= 2


# ---------------------------------------------------------------- offers and placement
async def to_review(client, who, aid: str) -> None:
    who.recruiter()
    await client.post(f"{API}/employer/applications/{aid}/advance")
    await client.post(f"{API}/employer/applications/{aid}/advance")


async def test_an_offer_accepted_and_the_candidate_placed(client, who, send_event, work, career, sessionmaker):
    job_id = await hiring_world(client, who, send_event, work, openings=1)
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    await work()
    await to_review(client, who, aid)
    assert (await client.post(f"{API}/employer/applications/{aid}/offer", json={"ctc": -1})).status_code == 422
    made = await client.post(f"{API}/employer/applications/{aid}/offer", json={"ctc": 900_000, "joining_date": "2026-11-15", "note": "Welcome aboard"})
    offer = made.json()["offer"]
    assert made.status_code == 201 and offer["ctc"] == 900_000 and offer["currency"] == "INR" and offer["status"] == "extended" and offer["role_title"] == "Backend Developer"
    assert (await client.post(f"{API}/employer/applications/{aid}/offer", json={"ctc": 950_000})).status_code == 409  # one offer per application
    who.student()
    mine = (await client.get(f"{API}/applications/{aid}")).json()["application"]
    assert mine["status"] == "offered" and mine["offer"]["ctc"] == 900_000 and mine["offer"]["joining_date"] == "2026-11-15"
    who.student(STUDENT_3)
    assert (await client.post(f"{API}/applications/{aid}/offer/respond", json={"accept": True})).status_code == 404
    who.student()
    accepted = await client.post(f"{API}/applications/{aid}/offer/respond", json={"accept": True, "note": "Thank you"})
    assert accepted.json()["offer"]["status"] == "accepted" and await status_of(client, who, aid) == "offer_accepted"
    assert (await client.post(f"{API}/applications/{aid}/offer/respond", json={"accept": False})).json()["code"] == "NO_OPEN_OFFER"
    who.recruiter()
    placed = (await client.post(f"{API}/employer/applications/{aid}/place")).json()["application"]
    assert placed["status"] == "placed"
    events_placed = await events(sessionmaker, "candidate.placed")
    assert len(events_placed) == 1 and events_placed[0]["user_id"] == str(STUDENT) and events_placed[0]["ctc"] == 900_000 and events_placed[0]["organization_id"]
    assert (await client.get(f"{API}/employer/jobs/{job_id}")).json()["job"]["status"] == "closed"  # the only opening is filled
    who.student()
    assert (await client.post(f"{API}/applications/{aid}/withdraw", json={})).status_code == 409
    assert [e["status"] for e in await events(sessionmaker, "offer.extended")] == ["extended"] and len(await events(sessionmaker, "offer.accepted")) == 1


async def test_a_declined_offer_and_a_withdrawal_during_an_offer(client, who, send_event, work, career):
    job_id = await hiring_world(client, who, send_event, work, students=(STUDENT, STUDENT_3), openings=2)
    a1 = await apply(client, who, job_id, career=career)
    a3 = await apply(client, who, job_id, user=STUDENT_3, career=career)
    await work()
    for application in (a1, a3):
        await to_review(client, who, application["application_id"])
        await client.post(f"{API}/employer/applications/{application['application_id']}/offer", json={"ctc": 800_000})
    who.student()
    declined = await client.post(f"{API}/applications/{a1['application_id']}/offer/respond", json={"accept": False})
    assert declined.json()["offer"]["status"] == "declined" and await status_of(client, who, a1["application_id"]) == "offer_declined"
    who.student(STUDENT_3)
    withdrawn = (await client.post(f"{API}/applications/{a3['application_id']}/withdraw", json={"note": "Joined elsewhere"})).json()["application"]
    assert withdrawn["status"] == "withdrawn" and withdrawn["offer"]["status"] == "declined"


async def test_an_unanswered_offer_expires(client, who, send_event, work, career, sessionmaker, settings):
    job_id = await hiring_world(client, who, send_event, work)
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    await work()
    await to_review(client, who, aid)
    await client.post(f"{API}/employer/applications/{aid}/offer", json={"ctc": 900_000, "valid_days": 3})
    assert await sweep_once(sessionmaker, settings) == (0, 0)  # still valid
    async with sessionmaker() as db:
        await db.execute(update(Offer).values(expires_at=utcnow() - timedelta(hours=1)))
        await db.commit()
    who.student()
    late = await client.post(f"{API}/applications/{aid}/offer/respond", json={"accept": True})
    assert late.status_code == 409 and late.json()["code"] == "OFFER_EXPIRED"
    assert await status_of(client, who, aid) == "offer_declined"
    async with sessionmaker() as db:
        assert (await db.execute(select(Offer.status))).scalar_one() == "expired" and (await db.execute(select(Application.decision_reason))).scalar_one() is None
    assert len(await events(sessionmaker, "offer.expired")) == 1
    assert await sweep_once(sessionmaker, settings) == (0, 0)


async def test_the_sweep_expires_offers_nobody_answered(client, who, send_event, work, career, sessionmaker, settings):
    job_id = await hiring_world(client, who, send_event, work)
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    await work()
    await to_review(client, who, aid)
    await client.post(f"{API}/employer/applications/{aid}/offer", json={"ctc": 900_000})
    async with sessionmaker() as db:
        await db.execute(update(Offer).values(expires_at=utcnow() - timedelta(hours=1)))
        await db.commit()
    assert await sweep_once(sessionmaker, settings) == (1, 0)
    assert await status_of(client, who, aid) == "offer_declined"
    who.student()
    history = (await client.get(f"{API}/applications/{aid}")).json()["application"]["history"]
    assert history[-1]["actor"] == "system" and history[-1]["note"] == "Offer expired unanswered"


async def test_rejecting_an_application_with_an_open_offer_withdraws_the_offer(client, who, send_event, work, career, sessionmaker):
    job_id = await hiring_world(client, who, send_event, work)
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    await work()
    await to_review(client, who, aid)
    await client.post(f"{API}/employer/applications/{aid}/offer", json={"ctc": 900_000})
    who.recruiter()
    assert (await client.post(f"{API}/employer/jobs/{job_id}/applications/reject", json={"application_ids": [aid], "reason": "Background check failed", "confirm": True})).status_code == 201
    async with sessionmaker() as db:
        assert (await db.execute(select(Offer.status))).scalar_one() == "withdrawn"


async def test_pipeline_work_stops_while_a_company_is_suspended(client, who, send_event, work, career):
    job_id = await hiring_world(client, who, send_event, work)
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    await work()
    who.manager()
    await client.post(f"{API}/admin/employers/{1755000000070011}/suspend", json={"note": "Investigation"})
    who.recruiter()
    frozen = await client.post(f"{API}/employer/applications/{aid}/advance")
    assert frozen.status_code == 409 and frozen.json()["code"] == "EMPLOYER_SUSPENDED"
    assert (await client.post(f"{API}/employer/jobs/{job_id}/applications/reject", json={"application_ids": [aid], "reason": "x", "confirm": True})).status_code == 409
    who.student()
    assert (await client.post(f"{API}/applications/{aid}/withdraw", json={})).status_code == 200  # a candidate can always leave
