from sqlalchemy import select

from app.models.outbox_event import OutboxEvent
from tests.conftest import (
    CERT,
    COURSE,
    JOB,
    STUDENT,
    STUDENT_2,
    attempt_payload,
    certificate_payload,
    fill_profile,
    seed_student,
)

API = "/api/v1"


async def outbox(sessionmaker, kind: str) -> list[dict]:
    async with sessionmaker() as db:
        return [r.payload for r in (await db.execute(select(OutboxEvent).where(OutboxEvent.event_type == kind).order_by(OutboxEvent.created_at))).scalars()]


async def ready_student(client, who, send_event) -> tuple[dict, str]:
    """A student with a full profile and one resume; returns (item ids, resume id)."""
    await seed_student(send_event)
    await send_event("certificate.issued", certificate_payload())
    await send_event("attempt.finalized", attempt_payload(1, percent=91.5))
    who.student()
    ids = await fill_profile(client)
    created = await client.post(f"{API}/resumes", json={"title": "Backend Developer", "target_role": "Backend Developer"})
    assert created.status_code == 201, created.text
    return ids, created.json()["resume"]["resume_id"]


# ---------------------------------------------------------------- create and read
async def test_templates_are_listed_and_all_ats_safe(client, who):
    who.student()
    templates = (await client.get(f"{API}/resume-templates")).json()["templates"]
    assert [t["key"] for t in templates] == ["classic", "compact", "modern"] and all(t["ats_safe"] for t in templates)


async def test_a_new_resume_starts_from_the_whole_profile(client, who, send_event):
    ids, rid = await ready_student(client, who, send_event)
    detail = (await client.get(f"{API}/resumes/{rid}")).json()
    assert [s["key"] for s in detail["draft"]["sections"]] == ["skills", "projects", "experience", "education", "certificates", "skill_scores", "achievements", "courses"]
    keys = {s["key"]: s for s in detail["document"]["sections"]}
    assert "courses" not in keys and keys["certificates"]["entries"][0]["verified"] is True
    assert keys["skills"]["entries"][0]["heading"] == "Python"
    assert detail["document"]["personal"]["name"] == "Asha Rao" and detail["document"]["personal"]["phone"] == "+91 98765 43210"
    assert detail["resume"]["template_key"] == "classic" and detail["resume"]["draft_revision"] == 0 and detail["resume"]["shared"] is False
    assert 0 < detail["ats"]["score"] <= 100 and ids
    blank = (await client.post(f"{API}/resumes", json={"title": "Blank", "blank": True})).json()["resume"]["resume_id"]
    assert (await client.get(f"{API}/resumes/{blank}")).json()["draft"]["sections"] == []


async def test_resumes_are_private_and_limited(client, who, send_event, settings):
    _, rid = await ready_student(client, who, send_event)
    who.student(STUDENT_2)
    assert (await client.get(f"{API}/resumes/{rid}")).status_code == 404
    assert (await client.get(f"{API}/resumes")).json()["resumes"] == []
    assert (await client.get(f"{API}/resumes/not-an-id")).status_code == 404
    who.staff()
    assert (await client.get(f"{API}/resumes")).status_code == 403
    who.student()
    assert len((await client.get(f"{API}/resumes")).json()["resumes"]) == 1
    for n in range(settings.MAX_RESUMES_PER_USER - 1):
        assert (await client.post(f"{API}/resumes", json={"title": f"R{n}"})).status_code == 201
    over = await client.post(f"{API}/resumes", json={"title": "one too many"})
    assert over.status_code == 409 and over.json()["code"] == "TOO_MANY_RESUMES"
    assert (await client.post(f"{API}/resumes", json={"title": "x y", "template_key": "nope"})).status_code in (409, 422)


# ---------------------------------------------------------------- editing
async def test_edit_reorders_sections_and_rewords_own_entries_only(client, who, send_event):
    ids, rid = await ready_student(client, who, send_event)
    detail = (await client.get(f"{API}/resumes/{rid}")).json()
    draft = detail["draft"]
    cert_id = next(i for s in draft["sections"] if s["key"] == "certificates" for i in [s["items"][0]["item_id"]])
    new = {
        "summary": {"text": "Backend developer who builds APIs in Python.", "visible": True}, "personal": {"show_phone": False, "show_location": True, "show_links": True},
        "sections": [
            {"key": "experience", "visible": True, "items": [{"item_id": ids["job"], "bullets": ["Built a REST API in Python serving 2000 requests per minute"]}]},
            {"key": "skills", "title": "Skills", "visible": True, "items": [{"item_id": ids["sql"]}, {"item_id": ids["py"]}]},
            {"key": "certificates", "visible": True, "items": [{"item_id": cert_id}]},
        ],
    }
    saved = await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": 0, "template_key": "modern", "draft": new})
    assert saved.status_code == 200 and saved.json()["resume"]["draft_revision"] == 1 and saved.json()["resume"]["template_key"] == "modern"
    doc = (await client.get(f"{API}/resumes/{rid}")).json()["document"]
    assert [s["key"] for s in doc["sections"]] == ["experience", "skills", "certificates"]
    assert doc["sections"][0]["entries"][0]["bullets"] == ["Built a REST API in Python serving 2000 requests per minute"]
    assert [e["heading"] for e in doc["sections"][1]["entries"]] == ["SQL", "Python"] and doc["personal"]["phone"] is None and doc["summary"].startswith("Backend developer")
    # the profile's own wording is untouched by the resume's override
    profile_job = next(i for i in (await client.get(f"{API}/profile")).json()["items"] if i["item_id"] == ids["job"])
    assert profile_job["data"]["bullets"] == JOB["bullets"]
    reword_verified = {**new, "sections": [{"key": "certificates", "visible": True, "items": [{"item_id": cert_id, "bullets": ["Grade: A+++"]}]}]}
    refused = await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": 1, "draft": reword_verified})
    assert refused.status_code == 422 and refused.json()["details"][0]["code"] == "VERIFIED_ITEM_READONLY"


async def test_draft_validation_rejects_foreign_wrong_and_duplicate_items(client, who, send_event):
    ids, rid = await ready_student(client, who, send_event)
    who.student(STUDENT_2)
    other = await client.post(f"{API}/profile/items", json={"kind": "skill", "data": {"name": "Rust"}})
    foreign = other.json()["item"]["item_id"]
    who.student()

    async def attempt(sections, revision=0):
        return await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": revision, "draft": {"sections": sections}})

    assert (await attempt([{"key": "skills", "items": [{"item_id": foreign}]}])).json()["details"][0]["code"] == "UNKNOWN_ITEM"
    assert (await attempt([{"key": "education", "items": [{"item_id": ids["py"]}]}])).json()["details"][0]["code"] == "WRONG_SECTION"
    assert (await attempt([{"key": "skills", "items": [{"item_id": ids["py"]}, {"item_id": ids["py"]}]}])).json()["details"][0]["code"] == "DUPLICATE_ITEM"
    assert (await attempt([{"key": "skills", "items": []}, {"key": "skills", "items": []}])).status_code == 422
    assert (await attempt([{"key": "summary", "items": []}])).status_code == 422
    assert (await attempt([{"key": "skills", "items": [{"item_id": ids["py"], "bullets": ["reworded skill"]}]}])).status_code == 422  # a skill has no bullets


async def test_stale_edits_are_refused(client, who, send_event):
    _, rid = await ready_student(client, who, send_event)
    first = await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": 0, "title": "Renamed"})
    assert first.status_code == 200
    stale = await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": 0, "title": "Lost update"})
    assert stale.status_code == 409 and stale.json()["code"] == "STALE_DRAFT"
    assert (await client.get(f"{API}/resumes/{rid}")).json()["resume"]["title"] == "Renamed"


async def test_deleted_or_revoked_things_disappear_from_the_document_not_the_draft(client, who, send_event):
    ids, rid = await ready_student(client, who, send_event)
    await client.delete(f"{API}/profile/items/{ids['proj']}")
    await send_event("certificate.revoked", {"certificate_id": str(CERT), "student_user_id": str(STUDENT), "course_id": str(COURSE), "reason": "integrity"})
    detail = (await client.get(f"{API}/resumes/{rid}")).json()
    assert {s["key"] for s in detail["document"]["sections"]} & {"projects", "certificates"} == set()
    assert "Library Manager" not in str(detail["document"])


async def test_duplicate_and_delete(client, who, send_event):
    _, rid = await ready_student(client, who, send_event)
    copy = (await client.post(f"{API}/resumes/{rid}/duplicate")).json()["resume"]
    assert copy["title"] == "Backend Developer (copy)" and copy["latest_version_no"] == 0 and copy["resume_id"] != rid
    assert (await client.delete(f"{API}/resumes/{copy['resume_id']}")).status_code == 200
    assert (await client.get(f"{API}/resumes/{copy['resume_id']}")).status_code == 404
    assert [r["resume_id"] for r in (await client.get(f"{API}/resumes")).json()["resumes"]] == [rid]


# ---------------------------------------------------------------- versions
async def test_versions_freeze_the_document_and_restore_without_loss(client, who, send_event, sessionmaker):
    ids, rid = await ready_student(client, who, send_event)
    v1 = (await client.post(f"{API}/resumes/{rid}/versions", json={"label": "First", "note": "for Acme"})).json()["version"]
    assert v1["version_no"] == 1 and v1["source"] == "manual" and v1["ats_score"] is not None and v1["label"] == "First"
    await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": 0, "draft": {"sections": [{"key": "skills", "items": [{"item_id": ids["py"]}]}]}})
    await client.delete(f"{API}/profile/items/{ids['job']}")  # the profile moves on
    v1_doc = (await client.get(f"{API}/resumes/{rid}/versions/1")).json()["document"]
    assert "Software Intern" in str(v1_doc)  # an old version keeps showing what it showed
    v2 = (await client.post(f"{API}/resumes/{rid}/versions", json={})).json()["version"]
    assert v2["version_no"] == 2 and [v["version_no"] for v in (await client.get(f"{API}/resumes/{rid}/versions")).json()["versions"]] == [2, 1]
    restored = await client.post(f"{API}/resumes/{rid}/versions/1/restore")
    assert restored.status_code == 200 and restored.json()["resume"]["draft_revision"] == 2
    detail = (await client.get(f"{API}/resumes/{rid}")).json()
    assert "experience" in [s["key"] for s in detail["draft"]["sections"]]  # the draft is back to version 1's
    numbers = [(v["version_no"], v["source"]) for v in (await client.get(f"{API}/resumes/{rid}/versions")).json()["versions"]]
    assert numbers == [(3, "restore"), (2, "manual"), (1, "manual")]  # restoring saved the draft it replaced
    assert (await client.get(f"{API}/resumes/{rid}/versions/9")).status_code == 404
    assert (await client.post(f"{API}/resumes/{rid}/versions/9/restore")).status_code == 404
    events = await outbox(sessionmaker, "resume.updated")
    assert [e["action"] for e in events] == ["version_saved", "version_saved", "version_saved", "restored"] and events[0]["version_no"] == 1 and events[0]["ats_score"] == v1["ats_score"]


async def test_old_versions_are_pruned_but_a_shared_one_survives(client, who, send_event, settings, sessionmaker):
    from app.models.resume import ResumeVersion

    _, rid = await ready_student(client, who, send_event)
    await client.post(f"{API}/resumes/{rid}/versions", json={})  # v1
    assert (await client.post(f"{API}/resumes/{rid}/share", json={"version_no": 1})).status_code == 200
    for _ in range(settings.MAX_VERSIONS_PER_RESUME + 2):
        await client.post(f"{API}/resumes/{rid}/versions", json={})
    async with sessionmaker() as db:
        kept = sorted((await db.execute(select(ResumeVersion.version_no))).scalars())
    assert len(kept) == settings.MAX_VERSIONS_PER_RESUME + 1 and kept[0] == 1  # the shared v1 was never pruned


# ---------------------------------------------------------------- scoring, gap, grammar
async def test_ats_report_with_and_without_a_job_description(client, who, send_event):
    _, rid = await ready_student(client, who, send_event)
    plain = (await client.post(f"{API}/resumes/{rid}/ats", json={})).json()["ats"]
    assert {c["key"] for c in plain["components"]} == {"contact", "sections", "bullets", "summary", "length", "template"} and plain["keywords"] == []
    jd = "Backend developer. Python, FastAPI, PostgreSQL, Docker, Kubernetes. Python and Docker every day."
    tailored = (await client.post(f"{API}/resumes/{rid}/ats", json={"job_description": jd})).json()["ats"]
    assert "keywords" in {c["key"] for c in tailored["components"]} and any(f["code"] == "MISSING_KEYWORDS" for f in tailored["fixes"])
    await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": 0, "job_description": jd})
    saved = (await client.post(f"{API}/resumes/{rid}/ats", json={})).json()["ats"]  # the one saved on the resume is used by default
    assert saved["score"] == tailored["score"]


async def test_keyword_gap_separates_what_the_profile_supports_from_what_it_lacks(client, who, send_event):
    ids, rid = await ready_student(client, who, send_event)
    await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": 0, "draft": {"sections": [{"key": "education", "items": []}]}})  # a resume that leaves the profile's skills out
    jd = "We need Python, SQL and Kubernetes. Kubernetes and Python are essential."
    gap = (await client.post(f"{API}/resumes/{rid}/keyword-gap", json={"job_description": jd})).json()["ats"]
    assert "python" in gap["add_from_profile"] and "sql" in gap["add_from_profile"]
    assert gap["not_in_profile"] == ["kubernetes"] and "only if" in gap["advice"] and 0 <= gap["match_percent"] < 100
    assert (await client.post(f"{API}/resumes/{rid}/keyword-gap", json={})).status_code == 422  # no job description anywhere
    assert ids


async def test_grammar_check_reads_own_words_only(client, who, send_event):
    ids, rid = await ready_student(client, who, send_event)
    await client.patch(f"{API}/profile/items/{ids['job']}", json={"data": {**JOB, "bullets": ["worked on the the login page", "Built the cart for 3 teams"]}})
    issues = (await client.post(f"{API}/resumes/{rid}/grammar")).json()["issues"]
    codes = {i["code"] for i in issues}
    assert {"REPEATED_WORD", "LOWERCASE_START", "WEAK_OPENING"} <= codes and all(i["item_id"] == ids["job"] for i in issues)


async def test_each_resume_action_is_its_own_matrix_cell(client, act_as) -> None:
    """A student left View + Create (no Update, no Delete) can make a resume and score it, but not edit or delete it,
    although the coarse career.profile key is still in their token."""
    from tests.conftest import ORG_A, STUDENT

    act_as(STUDENT, role="student", organization_id=ORG_A, defaults=False, scopes=("my_career.view", "my_career.create", "career.profile"))
    created = await client.post("/api/v1/resumes", json={"title": "Backend roles", "target_role": "Backend Developer"})
    assert created.status_code == 201, created.text
    resume_id = created.json()["resume"]["resume_id"]
    assert (await client.post(f"/api/v1/resumes/{resume_id}/ats", json={})).status_code == 200  # a check only reads
    assert (await client.patch(f"/api/v1/resumes/{resume_id}", json={"title": "Renamed"})).status_code == 403
    assert (await client.delete(f"/api/v1/resumes/{resume_id}")).status_code == 403
    act_as(STUDENT, role="student", organization_id=ORG_A)
    assert (await client.delete(f"/api/v1/resumes/{resume_id}")).status_code == 200
