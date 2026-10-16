from datetime import timedelta

from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.application import Application
from app.models.job import Job
from app.models.outbox_event import OutboxEvent
from tests.conftest import (
    API,
    COURSE_PY,
    ORG_A,
    ORG_B,
    RESUME,
    STUDENT,
    STUDENT_2,
    STUDENT_3,
    STUDENT_4,
    apply,
    hiring_world,
    profile_event,
)


async def events(sessionmaker, kind: str) -> list[dict]:
    async with sessionmaker() as db:
        return [r.payload for r in (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == kind).order_by(OutboxEvent.created_at))).scalars()]


# ---------------------------------------------------------------- applying
async def test_applying_freezes_the_resume_and_queues_screening(client, who, send_event, work, career, sessionmaker):
    job_id = await hiring_world(client, who, send_event, work)
    application = await apply(client, who, job_id)
    assert application["status"] == "applied" and application["job_title"] == "Backend Developer" and application["company_name"] == "Acme Labs"
    assert application["resume_version_no"] == 1 and application["match_score"] > 0 and application["match_explanation"][0] == "Matches 4/4 required skills"
    assert career.calls == [{"resume_id": RESUME, "user_id": str(STUDENT), "label": "Applied to Backend Developer"}]  # the resume was frozen by career-service
    assert application["history"][0]["to_status"] == "applied" and application["history"][0]["actor"] == "candidate"
    created = await events(sessionmaker, "application.created")
    assert len(created) == 1 and created[0]["application_id"] == application["application_id"] and created[0]["job_id"] == job_id and created[0]["user_id"] == str(STUDENT)
    await work()
    who.student()
    after = (await client.get(f"{API}/applications/{application['application_id']}")).json()["application"]
    assert after["status"] == "ai_screened" and [h["to_status"] for h in after["history"]] == ["applied", "ai_screened"] and after["history"][1]["actor"] == "system"
    assert "screening" not in after and "notes" not in after  # what the recruiter knows is not the candidate's to read


async def test_a_student_sees_their_applications_and_only_theirs(client, who, send_event, work, career):
    job_id = await hiring_world(client, who, send_event, work, students=(STUDENT, STUDENT_3))
    mine = await apply(client, who, job_id, career=career)
    await apply(client, who, job_id, user=STUDENT_3, career=career)
    who.student()
    listing = (await client.get(f"{API}/applications")).json()
    assert [a["application_id"] for a in listing["applications"]] == [mine["application_id"]] and listing["page_context"]["total_records"] == 1
    assert (await client.get(f"{API}/applications?status=placed")).json()["applications"] == []
    who.student(STUDENT_3)
    assert (await client.get(f"{API}/applications/{mine['application_id']}")).status_code == 404
    assert (await client.post(f"{API}/applications/{mine['application_id']}/withdraw", json={})).status_code == 404
    who.student()
    detail = (await client.get(f"{API}/job-board/{job_id}")).json()["job"]
    assert detail["applied"] is True and detail["application_id"] == mine["application_id"]


async def test_application_rules(client, who, send_event, work, career, sessionmaker):
    job_id = await hiring_world(
        client, who, send_event, work, students=(STUDENT, STUDENT_3, STUDENT_2), eligibility={"graduation_years": {"min": 2026, "max": 2026}, "institution_ids": [str(ORG_A)]}
    )
    await profile_event(send_event, STUDENT_3, ORG_A, graduation_year=2029, skills=("Python",), technologies=(), certificates=(COURSE_PY,), scores=((COURSE_PY, 80.0),))
    await work()

    async def try_apply(user, org, **body):
        career.owners[RESUME] = user
        who.student(user, org)
        return await client.post(f"{API}/job-board/{job_id}/apply", json={"resume_id": str(RESUME), **body})

    assert (await try_apply(STUDENT_4, ORG_A)).json()["code"] == "PROFILE_NOT_VERIFIED"  # no skill profile at all
    not_eligible = await try_apply(STUDENT_3, ORG_A)  # the wrong graduation year
    assert not_eligible.status_code == 403 and not_eligible.json()["code"] == "NOT_ELIGIBLE" and not_eligible.json()["details"][0]["message"] == "Open to graduation years 2026 (yours: 2029)."
    assert (await try_apply(STUDENT_2, ORG_B)).status_code == 404  # a restricted job does not exist for another institution
    first = await try_apply(STUDENT, ORG_A)
    assert first.status_code == 201
    again = await try_apply(STUDENT, ORG_A)
    assert again.status_code == 409 and again.json()["code"] == "ALREADY_APPLIED"
    async with sessionmaker() as db:
        assert len((await db.execute(select(Application))).scalars().all()) == 1


async def test_a_resume_that_is_not_theirs_or_a_career_outage_creates_no_application(client, who, send_event, work, career, sessionmaker):
    job_id = await hiring_world(client, who, send_event, work)
    who.student()
    career.owners[RESUME] = STUDENT_2  # somebody else's resume
    theirs = await client.post(f"{API}/job-board/{job_id}/apply", json={"resume_id": str(RESUME)})
    assert theirs.status_code == 422 and theirs.json()["details"][0]["code"] == "RESUME_NOT_FOUND"
    career.owners[RESUME] = STUDENT
    career.down = True
    down = await client.post(f"{API}/job-board/{job_id}/apply", json={"resume_id": str(RESUME)})
    assert down.status_code == 409 and down.json()["code"] == "RESUME_UNAVAILABLE"
    async with sessionmaker() as db:
        assert (await db.execute(select(Application))).scalars().all() == []
    career.down = False
    assert (await client.post(f"{API}/job-board/{job_id}/apply", json={"resume_id": str(RESUME)})).status_code == 201  # and they can simply try again


async def test_closed_paused_and_expired_jobs_take_no_applications(client, who, send_event, work, career, sessionmaker):
    job_id = await hiring_world(client, who, send_event, work)
    who.recruiter()
    await client.post(f"{API}/employer/jobs/{job_id}/pause")
    who.student()
    paused = await client.post(f"{API}/job-board/{job_id}/apply", json={"resume_id": str(RESUME)})
    assert paused.status_code == 409 and paused.json()["code"] == "JOB_NOT_OPEN"
    who.recruiter()
    await client.post(f"{API}/employer/jobs/{job_id}/resume")
    async with sessionmaker() as db:
        await db.execute(update(Job).values(deadline_at=utcnow() - timedelta(minutes=1)))
        await db.commit()
    who.student()
    late = await client.post(f"{API}/job-board/{job_id}/apply", json={"resume_id": str(RESUME)})
    assert late.status_code == 409 and late.json()["code"] == "DEADLINE_PASSED" and career.calls == []
    assert (await client.post(f"{API}/job-board/1755000000079999/apply", json={"resume_id": str(RESUME)})).status_code == 404


async def test_withdrawing(client, who, send_event, work):
    job_id = await hiring_world(client, who, send_event, work)
    application = await apply(client, who, job_id)
    who.student()
    done = await client.post(f"{API}/applications/{application['application_id']}/withdraw", json={"note": "Accepted another offer"})
    assert done.status_code == 200 and done.json()["application"]["status"] == "withdrawn" and done.json()["application"]["history"][-1]["note"] == "Accepted another offer"
    again = await client.post(f"{API}/applications/{application['application_id']}/withdraw", json={})
    assert again.status_code == 409 and again.json()["code"] == "APPLICATION_CLOSED"
    await work()  # a withdrawn application is not screened
    assert (await client.get(f"{API}/applications/{application['application_id']}")).json()["application"]["status"] == "withdrawn"
    who.recruiter()
    listed = (await client.get(f"{API}/employer/jobs/{job_id}/applications")).json()["applications"]
    assert listed[0]["status"] == "withdrawn" and listed[0]["decision_reason"] == "Accepted another offer" and listed[0]["screening"]["score"] is None


# ---------------------------------------------------------------- what the recruiter sees
async def test_recruiters_see_applicants_with_the_resume_as_sent_and_can_search_them(client, who, send_event, work, career):
    job_id = await hiring_world(client, who, send_event, work, students=(STUDENT, STUDENT_3))
    a1 = await apply(client, who, job_id, career=career)
    await apply(client, who, job_id, user=STUDENT_3, career=career)
    await work()
    who.recruiter()
    listing = (await client.get(f"{API}/employer/jobs/{job_id}/applications")).json()
    assert listing["page_context"]["total_records"] == 2 and {a["candidate"]["name"] for a in listing["applications"]} == {"Asha Rao", "Chitra Nair"}
    assert [a["candidate"]["name"] for a in (await client.get(f"{API}/employer/jobs/{job_id}/applications?q=chit")).json()["applications"]] == ["Chitra Nair"]
    assert (await client.get(f"{API}/employer/jobs/{job_id}/applications?q=%25")).json()["applications"] == []
    assert len((await client.get(f"{API}/employer/jobs/{job_id}/applications?status=ai_screened&status=applied&sort=match")).json()["applications"]) == 2
    assert (await client.get(f"{API}/employer/jobs/{job_id}/applications?min_score=101")).status_code == 422
    detail = (await client.get(f"{API}/employer/applications/{a1['application_id']}")).json()["application"]
    assert detail["candidate"] == {"user_id": str(STUDENT), "name": "Asha Rao", "email": "asha@example.com"} and detail["cover_note"] == "I would love to join."
    assert detail["resume"]["sections"][0]["entries"][0]["heading"] == "Software Intern" and detail["resume_version_no"] == 1
    assert detail["screening"]["source"] == "ai" and detail["screening"]["score"] is not None and [h["to_status"] for h in detail["history"]] == ["applied", "ai_screened"]
    funnel = (await client.get(f"{API}/employer/jobs/{job_id}/funnel")).json()
    assert funnel["by_status"] == {"ai_screened": 2} and funnel["total"] == 2 and funnel["placed"] == 0 and funnel["openings"] == 2


async def test_notes_are_private_to_the_recruiting_team(client, who, send_event, work, career):
    job_id = await hiring_world(client, who, send_event, work)
    application = await apply(client, who, job_id, career=career)
    who.recruiter()
    note = await client.post(f"{API}/employer/applications/{application['application_id']}/notes", json={"body": "Strong on APIs; ask about Docker."})
    assert note.status_code == 201 and note.json()["note"]["body"] == "Strong on APIs; ask about Docker."
    assert (await client.get(f"{API}/employer/applications/{application['application_id']}")).json()["application"]["notes"][0]["body"].startswith("Strong on APIs")
    who.student()
    assert "Strong on APIs" not in (await client.get(f"{API}/applications/{application['application_id']}")).text
    who.staff()
    assert (await client.get(f"{API}/employer/applications/{application['application_id']}")).status_code == 403


async def test_another_company_cannot_act_on_someone_elses_applicants_but_the_careers_manager_can(client, who, send_event, work, career):
    from tests.conftest import EMP_B, RECRUITER_B

    job_id = await hiring_world(client, who, send_event, work)
    application = await apply(client, who, job_id, career=career)
    aid = application["application_id"]
    who.recruiter(RECRUITER_B, EMP_B)
    for path in (f"/employer/applications/{aid}", f"/employer/jobs/{job_id}/applications", f"/employer/jobs/{job_id}/screening", f"/employer/jobs/{job_id}/funnel"):
        assert (await client.get(f"{API}{path}")).status_code == 404, path
    assert (await client.post(f"{API}/employer/applications/{aid}/advance")).status_code == 404
    assert (await client.post(f"{API}/employer/jobs/{job_id}/applications/shortlist", json={"application_ids": [aid]})).status_code == 404
    who.manager()  # the super admin runs hiring for every company: they see it and decide it
    assert (await client.get(f"{API}/employer/jobs/{job_id}/applications")).status_code == 200 and (await client.get(f"{API}/employer/applications/{aid}")).status_code == 200
    assert (await client.post(f"{API}/employer/applications/{aid}/advance")).status_code == 200
