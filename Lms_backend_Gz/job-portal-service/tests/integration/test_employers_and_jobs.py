from datetime import timedelta

from sqlalchemy import select

from app.models.outbox_event import OutboxEvent
from tests.conftest import (
    API,
    COURSE_PY,
    EMP_A,
    EMP_B,
    ORG_A,
    ORG_B,
    RECRUITER_B,
    job_body,
    open_job,
    org_payload,
    seed_world,
    verify_employer,
)


async def outbox(sessionmaker, kind: str) -> list[dict]:
    async with sessionmaker() as db:
        return [r.payload for r in (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == kind).order_by(OutboxEvent.created_at))).scalars()]


# ---------------------------------------------------------------- the company profile
async def test_a_company_is_verified_by_a_platform_admin_before_it_can_hire(client, who, send_event, sessionmaker):
    await seed_world(send_event)
    who.employer_admin()
    profile = (await client.get(f"{API}/employer/profile")).json()["employer"]
    assert profile["status"] == "draft" and profile["company_name"] == "Acme Labs" and profile["industry"] == "Software"
    early = await client.post(f"{API}/employer/profile/submit")
    assert early.status_code == 422 and {d["field"] for d in early.json()["details"]} == {"about", "website"}
    await client.patch(f"{API}/employer/profile", json={"about": "We build developer tools.", "website": "https://acme.example", "company_size": "51-200"})
    assert (await client.patch(f"{API}/employer/profile", json={"website": "not a link"})).status_code == 422
    assert (await client.post(f"{API}/employer/profile/submit")).json()["employer"]["status"] == "pending"
    assert (await client.post(f"{API}/employer/profile/submit")).status_code == 409  # already submitted
    who.recruiter()
    assert (await client.patch(f"{API}/employer/profile", json={"about": "x"})).status_code == 403  # only the admin edits the company
    who.student()
    assert (await client.get(f"{API}/employer/profile")).status_code == 403
    assert (await client.get(f"{API}/companies/{EMP_A}")).status_code == 404  # not public until verified
    who.manager()
    queue = (await client.get(f"{API}/admin/employers")).json()["employers"]
    assert [e["organization_id"] for e in queue] == [str(EMP_A)]
    rejected = await client.post(f"{API}/admin/employers/{EMP_A}/review", json={"approve": False})
    assert rejected.status_code == 422  # a rejection needs a reason
    assert (await client.post(f"{API}/admin/employers/{EMP_A}/review", json={"approve": False, "note": "Please add your registration number"})).json()["employer"]["status"] == "rejected"
    who.employer_admin()
    own = (await client.get(f"{API}/employer/profile")).json()["employer"]
    assert own["status"] == "rejected" and own["review_note"] == "Please add your registration number"
    assert (await client.patch(f"{API}/employer/profile", json={"about": "We build developer tools and hire responsibly."})).json()["employer"]["status"] == "draft"  # editing starts a new submission
    await client.post(f"{API}/employer/profile/submit")
    who.manager()
    assert (await client.post(f"{API}/admin/employers/{EMP_A}/review", json={"approve": True})).json()["employer"]["status"] == "verified"
    assert (await client.post(f"{API}/admin/employers/{EMP_A}/review", json={"approve": True})).status_code == 409
    who.student()
    public = await client.get(f"{API}/companies/{EMP_A}")
    assert public.status_code == 200 and public.json()["employer"]["company_name"] == "Acme Labs" and public.json()["employer"]["review_note"] is None
    who.other_admin()
    assert (await client.get(f"{API}/admin/employers")).status_code == 403
    types = [e["organization_id"] for e in await outbox(sessionmaker, "employer_profile.verified")]
    assert types == [str(EMP_A)] and len(await outbox(sessionmaker, "employer_profile.rejected")) == 1


# ---------------------------------------------------------------- drafting a job
async def test_a_job_needs_a_verified_company_and_a_complete_description(client, who, send_event):
    await seed_world(send_event)
    who.recruiter()
    created = await client.post(f"{API}/employer/jobs", json=job_body())
    job = created.json()["job"]
    assert created.status_code == 201 and job["status"] == "draft" and job["visibility"] == "public" and job["employer_id"] == str(EMP_A) and job["company_name"] == "Acme Labs"
    early = await client.post(f"{API}/employer/jobs/{job['job_id']}/submit")
    assert early.status_code == 409 and early.json()["code"] == "EMPLOYER_NOT_VERIFIED"
    await verify_employer(client, who)
    who.recruiter()
    thin = (await client.post(f"{API}/employer/jobs", json=job_body(description="Too short", required_skills=[]))).json()["job"]["job_id"]
    problems = await client.post(f"{API}/employer/jobs/{thin}/submit")
    assert problems.status_code == 422 and {d["field"] for d in problems.json()["details"]} == {"required_skills", "description"}
    assert (await client.post(f"{API}/employer/jobs/{job['job_id']}/submit")).json()["job"]["status"] == "pending_approval"


async def test_job_input_is_validated(client, who, send_event):
    await seed_world(send_event)
    who.recruiter()
    for bad in (
        job_body(title="ab"), job_body(locations=[], location_type="onsite"), job_body(ctc_min=900, ctc_max=100), job_body(experience_min_months=24, experience_max_months=12),
        job_body(deadline_at="2030-01-01T00:00:00"), job_body(eligibility={"graduation_years": {}}), job_body(eligibility={"graduation_years": {"min": 2028, "max": 2026}}),
        job_body(eligibility={"min_scores": [{"course_id": "1755000000071001", "min_percent": 140}]}), job_body(currency="rupees"), job_body(required_skills=["x"] * 31), job_body(unknown_field=1),
    ):
        assert (await client.post(f"{API}/employer/jobs", json=bad)).status_code == 422, bad
    remote = await client.post(f"{API}/employer/jobs", json=job_body(location_type="remote", locations=[]))
    assert remote.status_code == 201


async def test_jobs_belong_to_their_company(client, who, send_event):
    await seed_world(send_event)
    who.recruiter()
    job_id = (await client.post(f"{API}/employer/jobs", json=job_body())).json()["job"]["job_id"]
    assert [j["job_id"] for j in (await client.get(f"{API}/employer/jobs")).json()["jobs"]] == [job_id]
    who.recruiter(RECRUITER_B, EMP_B)
    assert (await client.get(f"{API}/employer/jobs/{job_id}")).status_code == 404 and (await client.patch(f"{API}/employer/jobs/{job_id}", json={"title": "Hijacked"})).status_code == 404
    assert (await client.get(f"{API}/employer/jobs")).json()["jobs"] == []
    who.student()
    assert (await client.get(f"{API}/employer/jobs")).status_code == 403
    who.manager()
    assert (await client.get(f"{API}/employer/jobs/{job_id}")).status_code == 200  # a careers manager may look at any company's job


async def test_eligibility_and_pipeline_are_stored_and_validated_at_submission(client, who, send_event, sessionmaker):
    await seed_world(send_event)
    await verify_employer(client, who)
    who.recruiter()
    rules = {"graduation_years": {"min": 2025, "max": 2026}, "certificate_course_ids": [str(COURSE_PY)], "min_scores": [{"course_id": str(COURSE_PY), "min_percent": 70}], "institution_ids": [str(ORG_A)]}
    pipeline = {"assessment": {"test_id": "1755000000072001", "min_percent": 60}, "ai_interview": {"plan_id": "1755000000072002"}, "hr_interview": True}
    job = (await client.post(f"{API}/employer/jobs", json=job_body(eligibility=rules, pipeline=pipeline))).json()["job"]
    assert job["visibility"] == "restricted" and job["institution_ids"] == [str(ORG_A)] and job["pipeline"] == {"assessment": {"test_id": "1755000000072001", "min_percent": 60.0}, "ai_interview": {"plan_id": "1755000000072002"}, "hr_interview": True}
    assert job["eligibility"]["graduation_years"] == {"min": 2025, "max": 2026} and job["eligibility"]["min_scores"] == [{"course_id": str(COURSE_PY), "min_percent": 70.0}]
    unknown_course = (await client.post(f"{API}/employer/jobs", json=job_body(eligibility={"certificate_course_ids": ["1755000000079999"]}))).json()["job"]["job_id"]
    bad = await client.post(f"{API}/employer/jobs/{unknown_course}/submit")
    assert bad.status_code == 422 and bad.json()["details"][0]["code"] == "UNKNOWN_COURSE"
    a_company = (await client.post(f"{API}/employer/jobs", json=job_body(eligibility={"institution_ids": [str(EMP_B)]}))).json()["job"]["job_id"]
    assert (await client.post(f"{API}/employer/jobs/{a_company}/submit")).json()["details"][0]["code"] == "UNKNOWN_INSTITUTION"  # a company is not an institution
    assert (await client.post(f"{API}/employer/jobs/{job['job_id']}/submit")).status_code == 200


# ---------------------------------------------------------------- approval and the lifecycle
async def test_approval_opens_the_job_and_announces_it(client, who, send_event, work, sessionmaker):
    await seed_world(send_event)
    await verify_employer(client, who)
    job_id = await open_job(client, who, work)
    who.manager()
    assert (await client.post(f"{API}/admin/jobs/{job_id}/review", json={"approve": True})).status_code == 409  # already open
    events = await outbox(sessionmaker, "job.published")
    assert len(events) == 1 and events[0]["job_id"] == job_id and events[0]["required_skills"] == ["Python", "FastAPI", "PostgreSQL", "Docker"] and events[0]["visibility"] == "public"
    who.recruiter()
    assert (await client.get(f"{API}/employer/jobs/{job_id}")).json()["job"]["status"] == "open"


async def test_a_rejected_job_returns_to_draft_with_the_reason(client, who, send_event):
    await seed_world(send_event)
    await verify_employer(client, who)
    who.recruiter()
    job_id = (await client.post(f"{API}/employer/jobs", json=job_body())).json()["job"]["job_id"]
    await client.post(f"{API}/employer/jobs/{job_id}/submit")
    assert (await client.patch(f"{API}/employer/jobs/{job_id}", json={"title": "Sneaky edit"})).status_code == 409  # no edits while pending
    who.manager()
    assert [j["job_id"] for j in (await client.get(f"{API}/admin/jobs")).json()["jobs"]] == [job_id]
    assert (await client.post(f"{API}/admin/jobs/{job_id}/review", json={"approve": False})).status_code == 422
    sent_back = (await client.post(f"{API}/admin/jobs/{job_id}/review", json={"approve": False, "note": "Please state the pay range"})).json()["job"]
    assert sent_back["status"] == "draft" and sent_back["review_note"] == "Please state the pay range"
    who.recruiter()
    assert (await client.patch(f"{API}/employer/jobs/{job_id}", json={"title": "Backend Developer II"})).status_code == 200
    assert (await client.post(f"{API}/employer/jobs/{job_id}/submit")).status_code == 200
    assert (await client.post(f"{API}/employer/jobs/{job_id}/withdraw-submission")).json()["job"]["status"] == "draft"
    who.recruiter(RECRUITER_B, EMP_B)
    assert (await client.post(f"{API}/employer/jobs/{job_id}/submit")).status_code == 404


async def test_pause_resume_close(client, who, send_event, work, sessionmaker):
    await seed_world(send_event)
    await verify_employer(client, who)
    job_id = await open_job(client, who, work)
    who.recruiter()
    assert (await client.post(f"{API}/employer/jobs/{job_id}/resume")).status_code == 409
    assert (await client.post(f"{API}/employer/jobs/{job_id}/pause")).json()["job"]["status"] == "paused"
    assert (await client.post(f"{API}/employer/jobs/{job_id}/pause")).status_code == 409
    assert (await client.patch(f"{API}/employer/jobs/{job_id}", json={"openings": 5})).json()["job"]["openings"] == 5  # a paused job can be edited
    assert (await client.post(f"{API}/employer/jobs/{job_id}/resume")).json()["job"]["status"] == "open"
    closed = (await client.post(f"{API}/employer/jobs/{job_id}/close", json={"reason": "Hired elsewhere"})).json()["job"]
    assert closed["status"] == "closed" and closed["closed_reason"] == "Hired elsewhere"
    assert (await client.post(f"{API}/employer/jobs/{job_id}/close", json={"reason": "again"})).status_code == 200  # idempotent
    assert (await client.patch(f"{API}/employer/jobs/{job_id}", json={"title": "x y z"})).status_code == 409
    assert (await client.post(f"{API}/employer/jobs/{job_id}/resume")).status_code == 409
    assert [e["reason"] for e in await outbox(sessionmaker, "job.closed")] == ["Hired elsewhere"]  # announced once


async def test_a_job_closes_itself_at_its_deadline(client, who, send_event, work, sessionmaker, settings):
    from sqlalchemy import update

    from app.core.time import utcnow
    from app.models.job import Job
    from app.worker.runner import sweep_once

    await seed_world(send_event)
    await verify_employer(client, who)
    job_id = await open_job(client, who, work)
    async with sessionmaker() as db:
        await db.execute(update(Job).values(deadline_at=utcnow() - timedelta(minutes=1)))
        await db.commit()
    who.student()
    assert (await client.get(f"{API}/job-board")).json()["jobs"] == []  # already hidden from students
    assert await sweep_once(sessionmaker, settings) == (0, 1)
    who.recruiter()
    closed = (await client.get(f"{API}/employer/jobs/{job_id}")).json()["job"]
    assert closed["status"] == "closed" and closed["closed_reason"] == "deadline passed"
    who.recruiter()
    assert (await client.post(f"{API}/employer/jobs/{job_id}/resume")).status_code == 409


# ---------------------------------------------------------------- suspending a company
async def test_suspending_an_employer_pauses_its_jobs_and_an_admins_suspension_needs_an_admin_to_lift(client, who, send_event, work):
    await seed_world(send_event)
    await verify_employer(client, who)
    job_id = await open_job(client, who, work)
    who.manager()
    assert (await client.post(f"{API}/admin/employers/{EMP_A}/suspend", json={"note": "Complaints"})).json()["employer"]["status"] == "suspended"
    who.recruiter()
    paused = (await client.get(f"{API}/employer/jobs/{job_id}")).json()["job"]
    assert paused["status"] == "paused"
    assert (await client.post(f"{API}/employer/jobs/{job_id}/resume")).json()["code"] == "EMPLOYER_NOT_VERIFIED"
    who.student()
    assert (await client.get(f"{API}/job-board")).json()["jobs"] == []
    await send_event("employer.activated", org_payload(EMP_A, "Acme Labs", "employer"))  # an account reactivation does not lift an admin's suspension
    who.manager()
    assert (await client.get(f"{API}/admin/employers?status=suspended")).json()["employers"][0]["organization_id"] == str(EMP_A)
    assert (await client.post(f"{API}/admin/employers/{EMP_A}/reinstate")).json()["employer"]["status"] == "verified"
    assert (await client.post(f"{API}/admin/employers/{EMP_A}/reinstate")).status_code == 409
    who.recruiter()
    assert (await client.post(f"{API}/employer/jobs/{job_id}/resume")).json()["job"]["status"] == "open"  # the employer resumes it


async def test_an_account_suspension_in_user_management_lifts_itself(client, who, send_event, work):
    await seed_world(send_event)
    await verify_employer(client, who)
    job_id = await open_job(client, who, work)
    await send_event("employer.suspended", org_payload(EMP_A, "Acme Labs", "employer", status="suspended"))
    who.recruiter()
    assert (await client.get(f"{API}/employer/jobs/{job_id}")).json()["job"]["status"] == "paused"
    who.employer_admin()
    assert (await client.get(f"{API}/employer/profile")).json()["employer"]["status"] == "suspended"
    await send_event("employer.activated", org_payload(EMP_A, "Acme Labs", "employer"))
    assert (await client.get(f"{API}/employer/profile")).json()["employer"]["status"] == "verified"
    who.recruiter()
    assert (await client.post(f"{API}/employer/jobs/{job_id}/resume")).status_code == 200


async def test_org_events_keep_names_and_types(send_event, sessionmaker):
    from app.models.refs import OrgRef

    await seed_world(send_event)
    await send_event("institution.updated", org_payload(ORG_A, "Anna University (Main)", "institution"))
    await send_event("institution.deleted", {"organization_id": str(ORG_B)})
    async with sessionmaker() as db:
        a, b, e = await db.get(OrgRef, ORG_A), await db.get(OrgRef, ORG_B), await db.get(OrgRef, EMP_A)
    assert (a.name, a.org_type, a.active) == ("Anna University (Main)", "institution", True) and b.active is False and (e.org_type, e.industry) == ("employer", "Software")


# ---------------------------------------------------------------- the super admin runs a company's hiring (no company logins)
async def test_the_super_admin_keeps_a_company_and_posts_its_jobs_directly(client, who, send_event):
    await seed_world(send_event)
    who.manager()
    early = await client.put(f"{API}/admin/employers/{EMP_A}/profile", json={"about": "We build developer tools."})
    assert early.status_code == 422 and {d["field"] for d in early.json()["details"]} == {"website"}  # industry comes from the company record
    kept = await client.put(f"{API}/admin/employers/{EMP_A}/profile", json={"about": "We build developer tools.", "website": "https://acme.example"})
    assert kept.status_code == 200 and kept.json()["employer"]["status"] == "verified"

    assert (await client.post(f"{API}/employer/jobs", json=job_body())).status_code == 422  # which company?
    assert (await client.post(f"{API}/employer/jobs", json=job_body(employer_org_id=str(ORG_A)))).status_code == 404  # an institution is not a company
    internship = job_body(employer_org_id=str(EMP_A), employment_type="internship", stipend_per_month=25_000, duration_months=6, title="Backend Intern")
    draft = await client.post(f"{API}/employer/jobs", json=internship)
    assert draft.status_code == 201, draft.text
    job = draft.json()["job"]
    assert job["employer_id"] == str(EMP_A) and job["stipend_per_month"] == 25_000 and job["duration_months"] == 6
    opened = await client.post(f"{API}/employer/jobs/{job['job_id']}/submit")
    assert opened.status_code == 200 and opened.json()["job"]["status"] == "open"  # no approval step for the super admin's own posting
    listed = (await client.get(f"{API}/employer/jobs", params={"employer_org_id": str(EMP_A)})).json()["jobs"]
    assert [j["job_id"] for j in listed] == [job["job_id"]]
    assert job["job_id"] in {j["job_id"] for j in (await client.get(f"{API}/employer/jobs")).json()["jobs"]}  # every company's
