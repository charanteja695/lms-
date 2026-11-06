import json

from sqlalchemy import select

from app.models.application import AiDecision
from app.models.outbox_event import OutboxEvent
from tests.conftest import API, COURSE_PY, ORG_A, STUDENT, STUDENT_3, STUDENT_4, apply, hiring_world, profile_event

WEAK = {"skills": ("HTML",), "technologies": (), "certificates": (COURSE_PY,), "scores": ((COURSE_PY, 50.0),), "roles": (), "titles": (), "months": 0}


async def screened(client, who, send_event, work, career, gateway, *, students=(STUDENT,), job=None):
    job_id = await hiring_world(client, who, send_event, work, students=students, **(job or {}))
    apps = {}
    for user in students:
        apps[user] = await apply(client, who, job_id, user=user, career=career)
    await work()
    return job_id, apps


async def detail(client, who, application_id):
    who.recruiter()
    return (await client.get(f"{API}/employer/applications/{application_id}")).json()["application"]


async def test_the_model_sees_an_anonymised_summary_and_never_a_person(client, who, send_event, work, career, gateway):
    job_id, apps = await screened(client, who, send_event, work, career, gateway)
    assert len(gateway.completions) == 1
    call = gateway.completions[0]
    assert call["prompt_key"] == "jobs.screen" and call["service"] == "job-portal-service" and call["organization_id"] == str(1755000000070011)  # the employer's own AI budget
    sent = json.dumps(call, ensure_ascii=False)
    for personal in ("Asha", "Rao", "asha@example.com", "98765", "github.com", "https://acme.example", "Anna University", "2025", "2026"):
        assert personal not in sent, personal
    content = call["messages"][0]["content"]
    assert '"Python"' in content and "APPLICANT:" in content and "[link]" in content and "[email]" in content and "[year]" not in content.split("APPLICANT:")[0]
    assert "Software Intern" in content and "Python Programming" in content  # the work and the verified course are what it judges on
    assert apps


async def test_a_screening_is_a_recommendation_logged_for_audit(client, who, send_event, work, career, gateway, sessionmaker):
    gateway.reply(json.dumps({"score": 90, "reasons": ["Strong Python and PostgreSQL", "Relevant internship"], "red_flags": ["No Docker project shown"]}))
    job_id, apps = await screened(client, who, send_event, work, career, gateway)
    application = await detail(client, who, apps[STUDENT]["application_id"])
    screening = application["screening"]
    assert application["status"] == "ai_screened" and screening["source"] == "ai" and screening["reasons"][:2] == ["Strong Python and PostgreSQL", "Relevant internship"]
    assert "No Docker project shown" in screening["red_flags"] and screening["recommendation"] == "shortlist" and screening["score"] >= 70
    async with sessionmaker() as db:
        decision = (await db.execute(select(AiDecision))).scalar_one()
        stored = json.dumps(decision.input)
    assert decision.source == "ai" and decision.model == "claude-sonnet-5" and decision.prompt_key == "jobs.screen" and decision.prompt_version == 3 and decision.ai_call_id == 1755000000099001
    assert len(decision.input_digest) == 64 and decision.recommendation == "shortlist" and decision.output["ai"]["score"] == 90 and "Asha" not in stored and "asha@example.com" not in stored
    who.recruiter()
    log = (await client.get(f"{API}/employer/jobs/{job_id}/screening/decisions")).json()["decisions"]
    assert log[0]["application_id"] == apps[STUDENT]["application_id"] and log[0]["prompt_version"] == 3 and log[0]["model"] == "claude-sonnet-5"
    async with sessionmaker() as db:
        types = [r.event_type for r in (await db.execute(select(OutboxEvent).order_by(OutboxEvent.created_at))).scalars()]
    assert "application.screened" in types


async def test_when_the_model_cannot_help_the_rules_stand_alone_and_say_so(client, who, send_event, work, career, gateway, sessionmaker):
    # one world, one applicant per failure mode
    job_id = await hiring_world(client, who, send_event, work, students=(STUDENT, STUDENT_3, STUDENT_4))
    modes = {STUDENT: ("down", (502, "PROVIDER_UNAVAILABLE")), STUDENT_3: ("unparseable", None), STUDENT_4: ("blocked", None)}
    for user, (name, error) in modes.items():
        gateway.completion_error, gateway.blocked = error, name == "blocked"
        gateway.replies.clear()
        if name == "unparseable":
            gateway.reply("I think they are great!")
        application = await apply(client, who, job_id, user=user, career=career)
        await work()
        screening = (await detail(client, who, application["application_id"]))["screening"]
        assert screening["source"] == "rules" and screening["score"] is not None and screening["reasons"], name
    async with sessionmaker() as db:
        decisions = (await db.execute(select(AiDecision))).scalars().all()
    assert {d.source for d in decisions} == {"rules"} and all(d.model is None and d.prompt_version is None for d in decisions)


async def test_ai_screening_can_be_switched_off(client, who, send_event, work, career, gateway, settings):
    settings.SCREEN_AI_ENABLED = False
    job_id, apps = await screened(client, who, send_event, work, career, gateway)
    assert gateway.completions == []
    assert (await detail(client, who, apps[STUDENT]["application_id"]))["screening"]["source"] == "rules" and job_id


async def test_red_flags_and_a_low_score_recommend_rejection_but_never_reject(client, who, send_event, work, career, gateway):
    job_id = await hiring_world(client, who, send_event, work, students=(STUDENT,), required_skills=["Kubernetes", "Terraform", "Go"], preferred_skills=[], experience_min_months=36)
    await profile_event(send_event, STUDENT_4, ORG_A, **WEAK)
    await work()
    gateway.reply(json.dumps({"score": 10, "reasons": ["Does not have the skills"], "red_flags": ["Missing core skills"]}))
    application = await apply(client, who, job_id, user=STUDENT_4, career=career)
    await work()
    row = await detail(client, who, application["application_id"])
    assert row["screening"]["recommendation"] == "reject" and row["screening"]["score"] < 40
    assert any(flag.startswith("Matches only 0 of 3 required skills") for flag in row["screening"]["red_flags"]) and "Experience is well below what the job asks for" in row["screening"]["red_flags"]
    assert row["status"] == "ai_screened"  # the AI's "reject" moved nobody
    assert row["history"][-1]["actor"] == "system" and row["history"][-1]["to_status"] == "ai_screened"


async def test_screening_ignores_withdrawn_applications_and_runs_once(client, who, send_event, work, career, gateway, sessionmaker, settings):
    from app.services.screening_service import ScreeningService

    job_id = await hiring_world(client, who, send_event, work, students=(STUDENT, STUDENT_3))
    withdrawn = await apply(client, who, job_id, career=career)
    who.student()
    await client.post(f"{API}/applications/{withdrawn['application_id']}/withdraw", json={})
    kept = await apply(client, who, job_id, user=STUDENT_3, career=career)
    await work()
    assert len(gateway.completions) == 1  # only the live application was screened
    async with sessionmaker() as db:
        service = ScreeningService(db, settings, None)
        assert await service.screen(int(withdrawn["application_id"])) is False
        assert await service.screen(int(kept["application_id"])) is False  # already screened
        assert await service.screen(1755000000079999) is False  # unknown
    assert len(gateway.completions) == 1


async def test_the_ranking_buckets_by_the_recruiters_thresholds_and_changes_nothing(client, who, send_event, work, career, gateway):
    job_id = await hiring_world(client, who, send_event, work, students=(STUDENT, STUDENT_3, STUDENT_4))
    await profile_event(send_event, STUDENT_3, ORG_A, skills=("Python",), technologies=(), certificates=(COURSE_PY,), scores=((COURSE_PY, 60.0),), roles=(), titles=(), months=0)
    await profile_event(send_event, STUDENT_4, ORG_A, **WEAK)
    await work()
    for user, score in ((STUDENT, 95), (STUDENT_3, 60), (STUDENT_4, 5)):
        gateway.reply(json.dumps({"score": score, "reasons": [f"ai {score}"], "red_flags": []}))
        await apply(client, who, job_id, user=user, career=career)
        await work()
    who.recruiter()
    ranking = (await client.get(f"{API}/employer/jobs/{job_id}/screening")).json()["ranking"]
    assert ranking["shortlist_at"] == 70 and ranking["reject_below"] == 40 and "recommendations" in ranking["note"]
    names = {bucket: [a["candidate"]["name"] for a in ranking[bucket]] for bucket in ("shortlist", "review", "reject", "unscreened")}
    assert names["shortlist"] == ["Asha Rao"] and names["reject"] == ["Dev Shah"] and names["unscreened"] == [] and names["review"] == ["Chitra Nair"]
    tight = (await client.get(f"{API}/employer/jobs/{job_id}/screening?shortlist_at=40&reject_below=10")).json()["ranking"]
    assert [a["candidate"]["name"] for a in tight["shortlist"]] == ["Asha Rao", "Chitra Nair"] and tight["reject"] == []
    assert (await client.get(f"{API}/employer/jobs/{job_id}/screening?shortlist_at=30&reject_below=60")).status_code == 422
    funnel = (await client.get(f"{API}/employer/jobs/{job_id}/funnel")).json()["by_status"]
    assert funnel == {"ai_screened": 3}  # reading the ranking decided nothing
