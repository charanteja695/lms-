from sqlalchemy import select

from app.models.outbox_event import OutboxEvent
from tests.conftest import (
    API,
    COURSE_PY,
    EMP_A,
    EMP_B,
    ORG_A,
    ORG_B,
    STUDENT,
    STUDENT_2,
    STUDENT_3,
    apply,
    hiring_world,
    job_body,
    open_job,
    profile_event,
    seed_world,
    verify_employer,
)


async def events(sessionmaker, kind: str) -> list[dict]:
    async with sessionmaker() as db:
        return [r.payload for r in (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == kind).order_by(OutboxEvent.created_at))).scalars()]


async def proposed_drive(client, who) -> str:
    who.head()
    response = await client.post(f"{API}/drives", json={"employer_id": str(EMP_A), "title": "Campus drive 2026", "description": "Backend roles", "drive_date": "2026-12-05"})
    assert response.status_code == 201, response.text
    return response.json()["drive"]["drive_id"]


async def accepted_drive(client, who) -> str:
    drive_id = await proposed_drive(client, who)
    who.employer_admin()
    assert (await client.post(f"{API}/drives/{drive_id}/respond", json={"accept": True})).json()["drive"]["status"] == "accepted"
    return drive_id


# ---------------------------------------------------------------- the invitation
async def test_a_head_invites_a_verified_company_and_the_company_answers(client, who, send_event, sessionmaker):
    await seed_world(send_event)
    who.head()
    unverified = await client.post(f"{API}/drives", json={"employer_id": str(EMP_A), "title": "Campus drive"})
    assert unverified.status_code == 422 and unverified.json()["details"][0]["code"] == "UNKNOWN_EMPLOYER"
    await verify_employer(client, who)
    drive_id = await proposed_drive(client, who)
    drive = (await client.get(f"{API}/drives/{drive_id}")).json()
    assert drive["drive"]["status"] == "proposed" and drive["drive"]["company_name"] == "Acme Labs" and drive["drive"]["institution_name"] == "Anna University" and drive["summary"]["jobs"] == 0
    who.staff()
    assert (await client.post(f"{API}/drives", json={"employer_id": str(EMP_A), "title": "Staff cannot"})).status_code == 403  # only the head invites
    assert (await client.get(f"{API}/drives")).json()["drives"][0]["drive_id"] == drive_id
    who.head(organization_id=ORG_B)
    assert (await client.get(f"{API}/drives/{drive_id}")).status_code == 404 and (await client.get(f"{API}/drives")).json()["drives"] == []
    who.employer_admin(organization_id=EMP_B)
    assert (await client.post(f"{API}/drives/{drive_id}/respond", json={"accept": True})).status_code == 404
    who.recruiter()
    assert (await client.post(f"{API}/drives/{drive_id}/respond", json={"accept": True})).status_code == 403  # the company's admin answers
    who.employer_admin()
    assert (await client.post(f"{API}/drives/{drive_id}/respond", json={"accept": False})).json()["drive"]["status"] == "declined"
    assert (await client.post(f"{API}/drives/{drive_id}/respond", json={"accept": True})).status_code == 409
    assert [e["status"] for e in await events(sessionmaker, "placement_drive.declined")] == ["declined"] and len(await events(sessionmaker, "placement_drive.proposed")) == 1


# ---------------------------------------------------------------- jobs in a drive
async def test_a_drives_jobs_are_only_for_that_institutions_students(client, who, send_event, work, sessionmaker):
    await seed_world(send_event)
    await profile_event(send_event, STUDENT, ORG_A, skills=("Python", "SQL"), technologies=("FastAPI", "PostgreSQL"), certificates=(COURSE_PY,), scores=((COURSE_PY, 90.0),))
    await profile_event(send_event, STUDENT_2, ORG_B, skills=("Python", "SQL"), technologies=("FastAPI", "PostgreSQL"), certificates=(COURSE_PY,), scores=((COURSE_PY, 90.0),))
    await verify_employer(client, who)
    drive_id = await proposed_drive(client, who)
    who.recruiter()
    job_id = await open_job(client, who, work)
    who.student(STUDENT_2, ORG_B)
    assert [j["job_id"] for j in (await client.get(f"{API}/job-board")).json()["jobs"]] == [job_id]  # public until it joins the drive
    who.recruiter()
    early = await client.post(f"{API}/drives/{drive_id}/jobs", json={"job_id": job_id})
    assert early.status_code == 409 and early.json()["code"] == "DRIVE_NOT_ACCEPTED"
    who.employer_admin()
    await client.post(f"{API}/drives/{drive_id}/respond", json={"accept": True})
    who.recruiter()
    other = await client.post(f"{API}/employer/jobs", json=job_body())
    assert (await client.post(f"{API}/drives/{drive_id}/jobs", json={"job_id": "1755000000079999"})).status_code == 404
    attached = await client.post(f"{API}/drives/{drive_id}/jobs", json={"job_id": job_id})
    assert attached.status_code == 200 and attached.json()["summary"]["jobs"] == 1
    await work()
    job = (await client.get(f"{API}/employer/jobs/{job_id}")).json()["job"]
    assert job["visibility"] == "restricted" and job["institution_ids"] == [str(ORG_A)] and job["drive_id"] == drive_id
    who.student(STUDENT_2, ORG_B)
    assert (await client.get(f"{API}/job-board")).json()["jobs"] == [] and (await client.get(f"{API}/job-board/{job_id}")).status_code == 404
    who.student()
    shown = (await client.get(f"{API}/job-board")).json()["jobs"]
    assert [j["job_id"] for j in shown] == [job_id] and shown[0]["drive_id"] == drive_id and (await client.get(f"{API}/recommendations")).json()["jobs"][0]["job_id"] == job_id
    assert other.status_code == 201
    who.recruiter(1755000000070113, EMP_B)
    assert (await client.post(f"{API}/drives/{drive_id}/jobs", json={"job_id": job_id})).status_code == 404  # not their drive


async def test_completing_and_cancelling_a_drive(client, who, send_event, work):
    await seed_world(send_event)
    await verify_employer(client, who)
    drive_id = await accepted_drive(client, who)
    who.recruiter()
    job_id = await open_job(client, who, work)
    who.recruiter()
    assert (await client.post(f"{API}/drives/{drive_id}/jobs", json={"job_id": job_id})).status_code == 200
    who.staff()
    assert (await client.post(f"{API}/drives/{drive_id}/cancel")).status_code == 403  # the head or the company's admin
    who.recruiter()
    assert (await client.post(f"{API}/drives/{drive_id}/complete")).status_code == 403
    who.head()
    cancelled = await client.post(f"{API}/drives/{drive_id}/cancel")
    assert cancelled.json()["drive"]["status"] == "cancelled" and cancelled.json()["summary"]["jobs"] == 1
    who.recruiter()
    closed = (await client.get(f"{API}/employer/jobs/{job_id}")).json()["job"]
    assert closed["status"] == "closed" and closed["closed_reason"] == "placement drive cancelled"  # it was only ever for this institution
    who.head()
    assert (await client.post(f"{API}/drives/{drive_id}/complete")).status_code == 409
    second = await proposed_drive(client, who)
    who.employer_admin()
    await client.post(f"{API}/drives/{second}/respond", json={"accept": True})
    assert (await client.post(f"{API}/drives/{second}/complete")).json()["drive"]["status"] == "completed"
    who.manager()
    assert len((await client.get(f"{API}/drives")).json()["drives"]) == 2
    who.recruiter()
    assert (await client.get(f"{API}/drives?status=completed")).json()["drives"][0]["drive_id"] == second


# ---------------------------------------------------------------- what an institution sees
async def test_an_institution_follows_its_students_applications_and_placements(client, who, send_event, work, career):
    job_id = await hiring_world(client, who, send_event, work, students=(STUDENT, STUDENT_3, STUDENT_2), openings=3)
    a1 = await apply(client, who, job_id, career=career)
    await apply(client, who, job_id, user=STUDENT_3, career=career)
    a2 = await apply(client, who, job_id, user=STUDENT_2, org=ORG_B, career=career)
    await work()
    who.recruiter()
    for application in (a1, a2):
        aid = application["application_id"]
        await client.post(f"{API}/employer/applications/{aid}/advance")
        await client.post(f"{API}/employer/applications/{aid}/advance")
        await client.post(f"{API}/employer/applications/{aid}/offer", json={"ctc": 800_000})
    who.student()
    await client.post(f"{API}/applications/{a1['application_id']}/offer/respond", json={"accept": True})
    who.recruiter()
    await client.post(f"{API}/employer/applications/{a1['application_id']}/place")
    who.staff()
    listing = (await client.get(f"{API}/institution/applications")).json()
    assert listing["page_context"]["total_records"] == 2 and {a["student"]["name"] for a in listing["applications"]} == {"Asha Rao", "Chitra Nair"}  # Ben studies elsewhere
    row = next(a for a in listing["applications"] if a["student"]["name"] == "Asha Rao")
    assert row["status"] == "placed" and row["company_name"] == "Acme Labs" and row["job_title"] == "Backend Developer" and row["ctc"] == 800_000 and row["currency"] == "INR"
    assert "screening" not in row and "notes" not in str(row) and "resume" not in row  # the employer's judgement is not the institution's to read
    assert [a["student"]["name"] for a in (await client.get(f"{API}/institution/applications?status=ai_screened")).json()["applications"]] == ["Chitra Nair"]
    assert [a["student"]["name"] for a in (await client.get(f"{API}/institution/placements")).json()["applications"]] == ["Asha Rao"]
    summary = (await client.get(f"{API}/institution/summary")).json()
    assert summary["students_applied"] == 2 and summary["applications"] == 2 and summary["placed"] == 1 and summary["placed_students"] == 1 and summary["employers"] == 1
    assert summary["by_status"] == {"placed": 1, "ai_screened": 1}
    who.head(organization_id=ORG_B)
    assert [a["student"]["name"] for a in (await client.get(f"{API}/institution/applications")).json()["applications"]] == ["Ben Iyer"]
    who.student()
    assert (await client.get(f"{API}/institution/applications")).status_code == 403
    who.recruiter()
    assert (await client.get(f"{API}/institution/summary")).status_code == 403


async def test_a_drives_numbers(client, who, send_event, work, career):
    await seed_world(send_event)
    await profile_event(send_event, STUDENT, ORG_A, skills=("Python", "SQL"), technologies=("FastAPI", "PostgreSQL"), certificates=(COURSE_PY,), scores=((COURSE_PY, 90.0),))
    await verify_employer(client, who)
    drive_id = await accepted_drive(client, who)
    who.recruiter()
    job_id = await open_job(client, who, work)
    who.recruiter()
    assert (await client.post(f"{API}/drives/{drive_id}/jobs", json={"job_id": job_id})).status_code == 200
    await work()
    application = await apply(client, who, job_id, career=career)
    await work()
    who.head()
    summary = (await client.get(f"{API}/drives/{drive_id}")).json()["summary"]
    assert summary == {"jobs": 1, "applications": 1, "by_status": {"ai_screened": 1}, "placed": 0}
    assert [a["application_id"] for a in (await client.get(f"{API}/institution/applications?drive_id={drive_id}")).json()["applications"]] == [application["application_id"]]
    assert (await client.get(f"{API}/institution/applications?drive_id=1755000000079999")).json()["applications"] == []
