from sqlalchemy import select

from app.models.match import JobMatch
from app.models.outbox_event import OutboxEvent
from tests.conftest import (
    API,
    COURSE_PY,
    COURSE_SQL,
    ORG_A,
    ORG_B,
    STUDENT,
    STUDENT_2,
    STUDENT_3,
    STUDENT_4,
    open_job,
    profile_event,
    seed_world,
    user_payload,
    verify_employer,
)

STRONG = {"skills": ("Python", "SQL", "Docker"), "technologies": ("FastAPI", "PostgreSQL"), "certificates": (COURSE_PY,), "scores": ((COURSE_PY, 95.0),)}
WEAK = {"skills": ("HTML",), "technologies": (), "certificates": (COURSE_SQL,), "scores": ((COURSE_SQL, 55.0),), "roles": ("Data Analyst",), "titles": ()}


async def world(client, who, send_event, work, **job):
    await seed_world(send_event)
    await profile_event(send_event, STUDENT, ORG_A, **STRONG)
    await profile_event(send_event, STUDENT_3, ORG_A, **WEAK)
    await profile_event(send_event, STUDENT_2, ORG_B, skills=("Python",), technologies=(), certificates=(COURSE_PY,), scores=((COURSE_PY, 70.0),))
    await verify_employer(client, who)
    return await open_job(client, who, work, **job)


async def recommendations(client, who, user=STUDENT, org=ORG_A) -> list[dict]:
    who.student(user, org)
    return (await client.get(f"{API}/recommendations")).json()["jobs"]


async def test_matching_is_eligibility_first_then_scored_with_an_explanation(client, who, send_event, work):
    await world(client, who, send_event, work)
    who.student()
    recs = (await client.get(f"{API}/recommendations")).json()["jobs"]
    assert len(recs) == 1
    match = recs[0]["match"]
    assert 50 <= match["score"] <= 100 and match["method"] == "dense" and set(match["breakdown"]) == {"skills", "semantic", "certificates", "preferences"}
    assert match["explanation"][0] == "Matches 4/4 required skills"
    assert recs[0]["eligibility_result"] == {"eligible": True, "reasons": []} and recs[0]["company_name"] == "Acme Labs" and recs[0]["applied"] is False
    assert any(line.startswith("Verified on the platform: Python") for line in match["explanation"])


async def test_students_are_ranked_and_a_weak_match_is_not_kept(client, who, send_event, work, sessionmaker):
    job_id = await world(client, who, send_event, work)
    async with sessionmaker() as db:
        scores = {m.user_id: m.score for m in (await db.execute(select(JobMatch))).scalars()}
    assert scores[STUDENT] > scores[STUDENT_2]  # verified Python at 95% beats 70%
    assert STUDENT_3 not in scores  # below the storing threshold: nothing to show
    who.student(STUDENT_2, ORG_B)
    assert (await client.get(f"{API}/recommendations")).json()["jobs"][0]["job_id"] == job_id
    who.student(STUDENT_3)
    assert (await client.get(f"{API}/recommendations")).json()["jobs"] == []
    listing = (await client.get(f"{API}/job-board")).json()["jobs"]  # still browsable, just without a match
    assert [j["job_id"] for j in listing] == [job_id] and listing[0]["match"] is None


async def test_a_large_cohort_is_matched_in_batches_and_the_work_queue_drains(client, who, send_event, work, sessionmaker, settings):
    from app.models.work import WorkItem

    await seed_world(send_event)
    for n in range(7):  # settings.MATCH_BATCH_SIZE is 3
        user = 1755000000075000 + n
        await send_event("user.created", user_payload(user, f"S{n}", "Test", "student", ORG_A))
        await profile_event(send_event, user, ORG_A, **STRONG)
    await verify_employer(client, who)
    await open_job(client, who, work, required_skills=["Python", "SQL"], preferred_skills=[])
    async with sessionmaker() as db:
        matched = {m.user_id for m in (await db.execute(select(JobMatch))).scalars()}
        pending = (await db.execute(select(WorkItem).where(WorkItem.status == "pending"))).scalars().all()
    assert matched == {1755000000075000 + n for n in range(7)} and pending == [] and settings.MATCH_BATCH_SIZE == 3


async def test_eligibility_rules_exclude_students_and_say_why(client, who, send_event, work):
    await seed_world(send_event)
    await profile_event(send_event, STUDENT, ORG_A, **STRONG)
    await profile_event(send_event, STUDENT_4, ORG_A, graduation_year=2028, **STRONG)
    await profile_event(send_event, STUDENT_2, ORG_B, skills=("Python",), technologies=(), certificates=(COURSE_PY,), scores=((COURSE_PY, 70.0),))
    await verify_employer(client, who)
    rules = {"graduation_years": {"min": 2025, "max": 2026}, "certificate_course_ids": [str(COURSE_PY)], "min_scores": [{"course_id": str(COURSE_PY), "min_percent": 90}]}
    job_id = await open_job(client, who, work, eligibility=rules)
    assert [j["job_id"] for j in await recommendations(client, who)] == [job_id]
    assert await recommendations(client, who, STUDENT_4) == []  # 2028 graduates are not in scope
    who.student(STUDENT_4)
    shown = (await client.get(f"{API}/job-board/{job_id}")).json()["job"]
    assert shown["eligibility_result"] == {"eligible": False, "reasons": ["Open to graduation years 2025–2026 (yours: 2028)."]} and shown["match"] is None
    assert (await client.get(f"{API}/job-board?eligible_only=true")).json()["jobs"] == []
    who.student(STUDENT_2, ORG_B)  # 70% is below the 90% asked for
    assert (await client.get(f"{API}/job-board/{job_id}")).json()["job"]["eligibility_result"]["reasons"] == ["Requires at least 90% in Python Programming (yours: 70%)."]


async def test_a_restricted_job_is_seen_only_by_its_institutions_students(client, who, send_event, work):
    await seed_world(send_event)
    await profile_event(send_event, STUDENT, ORG_A, **STRONG)
    await profile_event(send_event, STUDENT_2, ORG_B, **STRONG)
    await verify_employer(client, who)
    job_id = await open_job(client, who, work, eligibility={"institution_ids": [str(ORG_A)]})
    assert [j["job_id"] for j in await recommendations(client, who)] == [job_id]
    assert await recommendations(client, who, STUDENT_2, ORG_B) == []
    who.student(STUDENT_2, ORG_B)
    assert (await client.get(f"{API}/job-board")).json()["jobs"] == [] and (await client.get(f"{API}/job-board/{job_id}")).status_code == 404
    await send_event("user.updated", user_payload(STUDENT_2, "Ben", "Iyer", "student", ORG_A))  # transferred to the institution
    await send_event("skill_profile.updated", {"user_id": str(STUDENT_2), "organization_id": str(ORG_A), "revision": 99, "facts": STRONG_FACTS})
    await work()
    who.student(STUDENT_2, ORG_A)
    assert [j["job_id"] for j in (await client.get(f"{API}/recommendations")).json()["jobs"]] == [job_id]


STRONG_FACTS = {
    "skills": ["Python", "SQL"], "technologies": ["FastAPI"], "job_titles": [], "experience_months": 0, "education": [{"degree": "B.Tech", "field": "CS", "end_year": 2026}], "graduation_year": 2026,
    "certificates": [str(COURSE_PY)], "scores": [{"course_id": str(COURSE_PY), "best_percent": 90}], "location": "Chennai", "target_roles": [], "headline": None,
}


async def test_preferences_move_the_score_and_opting_out_removes_recommendations(client, who, send_event, work, sessionmaker):
    await world(client, who, send_event, work)
    who.student()
    before = (await client.get(f"{API}/recommendations")).json()["jobs"][0]["match"]["breakdown"]["preferences"]
    assert (await client.get(f"{API}/job-preferences")).json()["preferences"] == {"locations": [], "open_to_remote": True, "roles": [], "min_ctc": None, "employment_types": [], "open_to_work": True}
    saved = await client.put(f"{API}/job-preferences", json={"locations": ["Delhi"], "open_to_remote": False, "min_ctc": 5_000_000, "employment_types": ["internship"]})
    assert saved.status_code == 200 and saved.json()["preferences"]["locations"] == ["Delhi"]
    await work()
    after = (await client.get(f"{API}/recommendations")).json()["jobs"]
    assert after and after[0]["match"]["breakdown"]["preferences"] < before
    assert {"Location differs from your preference", "Pay is below your minimum", "Not a kind of job you asked for"} <= set(after[0]["match"]["explanation"])
    await client.put(f"{API}/job-preferences", json={"open_to_work": False})
    await work()
    assert (await client.get(f"{API}/recommendations")).json()["jobs"] == []
    async with sessionmaker() as db:
        assert STUDENT not in {m.user_id for m in (await db.execute(select(JobMatch))).scalars()}
    assert (await client.put(f"{API}/job-preferences", json={"min_ctc": -5})).status_code == 422 and (await client.put(f"{API}/job-preferences", json={"employment_types": ["gig"]})).status_code == 422


async def test_a_student_hears_about_a_strong_match_once(client, who, send_event, work, sessionmaker):
    await seed_world(send_event)
    await profile_event(send_event, STUDENT, ORG_A, **STRONG)
    await verify_employer(client, who)
    job_id = await open_job(client, who, work, required_skills=["Python", "SQL"], preferred_skills=[])

    async def announcements() -> list[dict]:
        async with sessionmaker() as db:
            return [r.payload for r in (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == "job.match_found"))).scalars()]

    first = await announcements()
    assert len(first) == 1 and first[0]["user_id"] == str(STUDENT) and first[0]["job_id"] == job_id and first[0]["score"] >= 70
    await profile_event(send_event, STUDENT, ORG_A, **{**STRONG, "skills": ("Python", "SQL", "Docker", "Git")})
    who.recruiter()
    await client.patch(f"{API}/employer/jobs/{job_id}", json={"preferred_skills": ["Git"]})
    await work()
    assert len(await announcements()) == 1  # re-scoring does not tell them again


async def test_editing_an_open_job_rematches_it(client, who, send_event, work):
    job_id = await world(client, who, send_event, work)
    who.student()
    before = (await client.get(f"{API}/recommendations")).json()["jobs"][0]["match"]
    who.recruiter()
    await client.patch(f"{API}/employer/jobs/{job_id}", json={"required_skills": ["Python", "SQL", "Docker", "Kubernetes", "Terraform"]})
    await work()
    who.student()
    after = (await client.get(f"{API}/recommendations")).json()["jobs"][0]["match"]
    assert after["explanation"][0] == "Matches 3/5 required skills; missing: Kubernetes, Terraform" and after["score"] < before["score"]
    who.recruiter()
    await client.patch(f"{API}/employer/jobs/{job_id}", json={"openings": 9})  # nothing a match depends on: no re-score needed
    assert (await client.post(f"{API}/employer/jobs/{job_id}/pause")).status_code == 200
    who.student()
    assert (await client.get(f"{API}/recommendations")).json()["jobs"] == []  # a paused job is not recommended


async def test_semantic_similarity_uses_embeddings_when_the_gateway_answers_and_words_when_it_does_not(client, who, send_event, work, gateway, sessionmaker):
    await seed_world(send_event)
    await profile_event(send_event, STUDENT, ORG_A, **STRONG)
    await profile_event(send_event, STUDENT_3, ORG_A, **STRONG)
    await verify_employer(client, who)
    gateway.embedding_error = (503, "PROVIDER_UNAVAILABLE")
    await open_job(client, who, work)
    async with sessionmaker() as db:
        assert {m.semantic_method for m in (await db.execute(select(JobMatch))).scalars()} == {"lexical"}
    gateway.embedding_error = None
    await profile_event(send_event, STUDENT, ORG_A, **{**STRONG, "skills": ("Python", "SQL", "Docker", "Git")})  # a new profile revision queues a re-score
    await work()
    async with sessionmaker() as db:
        methods = {m.user_id: m.semantic_method for m in (await db.execute(select(JobMatch))).scalars()}
    assert methods[STUDENT] == "dense" and gateway.embeddings  # embeddings were requested for the job and the profile
    embedded_texts = " ".join(t for batch in gateway.embeddings for t in batch)
    assert "Asha" not in embedded_texts and "asha@example.com" not in embedded_texts  # nothing personal is embedded


async def test_a_profile_without_verified_items_gets_no_recommendations(client, who, send_event, work):
    await seed_world(send_event)
    await profile_event(send_event, STUDENT, ORG_A, certificates=(), scores=(), skills=("Python", "SQL", "Docker"), technologies=("FastAPI", "PostgreSQL"))
    await verify_employer(client, who)
    await open_job(client, who, work, required_skills=["Python", "SQL"], preferred_skills=[])
    who.student()
    assert (await client.get(f"{API}/recommendations")).json()["jobs"][0]["match"]["score"] > 0  # matching itself only needs a profile: the rule is at apply time
    who.student(STUDENT_4)
    jobs = (await client.get(f"{API}/job-board")).json()["jobs"]
    assert jobs[0]["eligibility_result"]["eligible"] is False and "Build your skill profile" in jobs[0]["eligibility_result"]["reasons"][0]  # no profile at all


async def test_browse_and_search(client, who, send_event, work):
    await seed_world(send_event)
    await profile_event(send_event, STUDENT, ORG_A, **STRONG)
    await verify_employer(client, who)
    backend = await open_job(client, who, work, title="Backend Developer", locations=["Chennai", "Pune"], ctc_max=1_200_000)
    data = await open_job(client, who, work, title="Data Analyst Intern", employment_type="internship", locations=["Bengaluru"], required_skills=["SQL", "Excel"], preferred_skills=[], ctc_min=100_000, ctc_max=300_000, description="Analyse data with SQL and build dashboards for the sales team. Learn from a friendly analytics group.")
    remote = await open_job(client, who, work, title="Support Engineer", location_type="remote", locations=[], required_skills=["Linux"], preferred_skills=[], ctc_min=300_000, ctc_max=700_000, description="Help customers run our developer tools; debug on Linux; write clear replies to tickets every day.")
    who.student()

    async def ids(query: str) -> list[str]:
        return [j["job_id"] for j in (await client.get(f"{API}/job-board?{query}")).json()["jobs"]]

    assert set(await ids("")) == {backend, data, remote}
    assert (await ids("sort=relevance"))[0] == backend  # the best match first
    assert await ids("q=analyst") == [data] and await ids("q=dashboards") == [data]  # title and description
    assert await ids("location=pune") == [backend] and await ids("employment_type=internship") == [data] and await ids("location_type=remote") == [remote]
    assert await ids("skill=sql") == [data]
    assert await ids("skill=Excel") == [data] and await ids("skill=cobol") == []
    assert set(await ids("min_ctc=800000")) == {backend} and (await ids("sort=pay"))[0] == backend
    assert await ids("q=%25") == []  # a wildcard is just text
    page2 = (await client.get(f"{API}/job-board?per_page=2&page=2")).json()
    assert len(page2["jobs"]) == 1 and page2["page_context"]["total_records"] == 3
    assert (await client.get(f"{API}/job-board/1755000000079999")).status_code == 404 and (await client.get(f"{API}/job-board/nope")).status_code == 404
    who.recruiter()
    assert (await client.get(f"{API}/job-board")).status_code == 403
