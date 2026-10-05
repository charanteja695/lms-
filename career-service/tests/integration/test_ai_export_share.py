import json
from datetime import timedelta

from sqlalchemy import select, update

from app.core.time import utcnow
from app.models.resume import Resume
from app.worker.runner import housekeeping_once
from tests.conftest import STUDENT_2
from tests.integration.test_resumes import outbox, ready_student

API = "/api/v1"


# ---------------------------------------------------------------- AI suggestions
async def test_a_faithful_summary_is_applicable(client, who, send_event, gateway):
    _, rid = await ready_student(client, who, send_event)
    gateway.reply("Computer science graduate with Python and SQL skills, a backend internship at Acme Labs, and a certified Python Programming course.")
    response = await client.post(f"{API}/resumes/{rid}/ai/summary", json={"tone": "warm"})
    suggestion = response.json()["suggestion"]
    assert response.status_code == 200 and suggestion["applicable"] is True and suggestion["warnings"] == []
    call = gateway.requests[0]
    assert call["prompt_key"] == "career.summary" and call["service"] == "career-service" and call["variables"] == {"target_role": "Backend Developer", "tone": "warm"}
    facts = call["messages"][0]["content"]
    assert "(verified) Certificate: Python Programming" in facts and "(self-declared) Skill: Python" in facts and "Acme Labs" in facts  # marked, and complete
    assert call["organization_id"]


async def test_an_invented_credential_makes_the_suggestion_not_applicable(client, who, send_event, gateway):
    _, rid = await ready_student(client, who, send_event)
    gateway.reply("Backend developer with 5 years of experience at Google, holding an AWS Solutions Architect certificate, fluent in Kubernetes.")
    suggestion = (await client.post(f"{API}/resumes/{rid}/ai/summary", json={})).json()["suggestion"]
    assert suggestion["applicable"] is False
    found = {(w["type"], w["value"]) for w in suggestion["warnings"]}
    assert ("number", "5") in found and ("name", "google") in found and ("name", "aws") in found and ("name", "kubernetes") in found


async def test_nothing_from_a_model_is_ever_saved(client, who, send_event, gateway):
    _, rid = await ready_student(client, who, send_event)
    before = (await client.get(f"{API}/resumes/{rid}")).json()
    gateway.reply("Invented nonsense with 99 awards.")
    await client.post(f"{API}/resumes/{rid}/ai/summary", json={})
    after = (await client.get(f"{API}/resumes/{rid}")).json()
    assert after["draft"] == before["draft"] and after["resume"]["draft_revision"] == before["resume"]["draft_revision"] and "99 awards" not in str(after)


async def test_summary_needs_facts(client, who, gateway):
    who.student()
    rid = (await client.post(f"{API}/resumes", json={"title": "Empty"})).json()["resume"]["resume_id"]
    response = await client.post(f"{API}/resumes/{rid}/ai/summary", json={})
    assert response.status_code == 422 and response.json()["code"] == "NO_FACTS" and gateway.requests == []


async def test_rewrite_checks_each_bullet_and_never_adds_a_metric(client, who, send_event, gateway):
    _, rid = await ready_student(client, who, send_event)
    gateway.reply("1. Built a REST API in Python serving 2000 requests per minute\n2. Reduced checkout failures by 60%\n3. Wrote automated tests")
    body = {"bullets": ["worked on a REST API in Python that served 2000 requests per minute", "fixed checkout bugs", "worked on tests"], "context": "Software Intern at Acme Labs"}
    results = (await client.post(f"{API}/resumes/{rid}/ai/rewrite", json=body)).json()["suggestions"]
    assert [r["original"] for r in results] == body["bullets"]
    assert results[0]["applicable"] is True and results[0]["metric_prompt"] is None
    assert results[1]["applicable"] is False and results[1]["warnings"] == [{"type": "number", "value": "60"}]
    assert results[2]["applicable"] is True and "add it in your own words" in results[2]["metric_prompt"]
    call = gateway.requests[0]
    assert call["prompt_key"] == "career.rewrite" and "1. worked on a REST API" in call["messages"][0]["content"]


async def test_rewrite_with_the_wrong_number_of_lines_is_an_error_not_a_guess(client, who, send_event, gateway):
    _, rid = await ready_student(client, who, send_event)
    gateway.reply("Only one line came back")
    response = await client.post(f"{API}/resumes/{rid}/ai/rewrite", json={"bullets": ["a b c d", "e f g h"]})
    assert response.status_code == 503 and response.json()["code"] == "AI_BAD_OUTPUT"


async def test_polish_and_tailor(client, who, send_event, gateway):
    _, rid = await ready_student(client, who, send_event)
    gateway.reply("Built the login page for 5 teams.")
    polished = (await client.post(f"{API}/resumes/{rid}/ai/polish", json={"text": "built the the login page for 3 teams"})).json()["suggestion"]
    assert polished["original"] == "built the the login page for 3 teams" and polished["applicable"] is False
    assert polished["warnings"] == [{"type": "number", "value": "5"}]  # the polish changed a fact: reported, not trusted
    jd = "Backend developer: Python, SQL and Kubernetes. Kubernetes is essential."
    without = (await client.post(f"{API}/resumes/{rid}/ai/tailor", json={"job_description": jd})).json()["suggestion"]
    assert without["summary"] is None and without["gap"]["not_in_profile"] == ["kubernetes"] and len(gateway.requests) == 1  # no model call unless asked
    gateway.reply("Backend developer skilled in Python and SQL.")
    with_summary = (await client.post(f"{API}/resumes/{rid}/ai/tailor", json={"job_description": jd, "include_summary": True})).json()["suggestion"]
    assert with_summary["summary"]["applicable"] is True
    assert "Emphasise these" in gateway.requests[-1]["messages"][0]["content"] and "kubernetes" not in gateway.requests[-1]["messages"][0]["content"].split("Emphasise")[1]
    gateway.reply("Backend developer skilled in Python, SQL and Kubernetes.")
    lying = (await client.post(f"{API}/resumes/{rid}/ai/tailor", json={"job_description": jd, "include_summary": True})).json()["suggestion"]["summary"]
    assert lying["applicable"] is False and ("keyword", "kubernetes") in {(w["type"], w["value"]) for w in lying["warnings"]}
    assert (await client.post(f"{API}/resumes/{rid}/ai/tailor", json={})).status_code == 422


async def test_gateway_failures_become_clear_errors(client, who, send_event, gateway):
    _, rid = await ready_student(client, who, send_event)
    for status, code, expected_status, expected_code in ((429, "QUOTA_EXCEEDED", 429, "QUOTA_EXCEEDED"), (403, "AI_DISABLED", 403, "AI_DISABLED"), (502, "PROVIDER_UNAVAILABLE", 503, "AI_UNAVAILABLE"), (404, "PROMPT_NOT_FOUND", 503, "AI_UNAVAILABLE")):
        gateway.error = (status, code)
        response = await client.post(f"{API}/resumes/{rid}/ai/polish", json={"text": "some text to fix"})
        assert (response.status_code, response.json()["code"]) == (expected_status, expected_code)
    gateway.error = None
    gateway.blocked = True
    blocked = await client.post(f"{API}/resumes/{rid}/ai/polish", json={"text": "some text to fix"})
    assert blocked.status_code == 422 and blocked.json()["code"] == "AI_CONTENT_BLOCKED"
    who.student(STUDENT_2)
    assert (await client.post(f"{API}/resumes/{rid}/ai/polish", json={"text": "some text to fix"})).status_code == 404  # not their resume


# ---------------------------------------------------------------- export
async def test_pdf_export_of_the_draft_and_of_a_version(client, who, send_event):
    _, rid = await ready_student(client, who, send_event)
    pdf = await client.get(f"{API}/resumes/{rid}/export/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF") and len(pdf.content) > 2000
    assert 'filename="Backend-Developer.pdf"' in pdf.headers["content-disposition"] and pdf.headers["x-unrenderable-characters"] == "0" and pdf.headers["cache-control"] == "private, no-store"
    await client.post(f"{API}/resumes/{rid}/versions", json={})
    assert (await client.get(f"{API}/resumes/{rid}/export/pdf?version_no=1")).status_code == 200
    assert (await client.get(f"{API}/resumes/{rid}/export/pdf?version_no=7")).status_code == 404
    await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": 0, "title": "आशा resume"})
    who.student(STUDENT_2)
    assert (await client.get(f"{API}/resumes/{rid}/export/pdf")).status_code == 404


async def test_unrenderable_characters_are_reported_not_hidden(client, who, send_event, sessionmaker):
    _, rid = await ready_student(client, who, send_event)
    await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": 0, "draft": {"summary": {"text": "आशा is a developer", "visible": True}, "sections": []}})
    assert (await client.get(f"{API}/resumes/{rid}/export/pdf")).headers["x-unrenderable-characters"] == "3"


async def test_json_resume_export(client, who, send_event):
    _, rid = await ready_student(client, who, send_event)
    response = await client.get(f"{API}/resumes/{rid}/export/json-resume")
    body = json.loads(response.content)
    assert response.headers["content-disposition"] == 'attachment; filename="resume.json"'
    assert body["basics"]["name"] == "Asha Rao" and body["work"][0]["name"] == "Acme Labs" and body["education"][0]["institution"] == "Anna University"
    assert body["certificates"][0]["name"] == "Python Programming — Certificate" and {i["kind"] for i in body["x-lms"]["verified_items"]} == {"certificate", "skill_score"}


# ---------------------------------------------------------------- share
async def test_a_share_link_is_pinned_to_a_version_and_hides_contact_by_default(client, who, send_event, sessionmaker):
    ids, rid = await ready_student(client, who, send_event)
    shared = (await client.post(f"{API}/resumes/{rid}/share", json={})).json()["share"]
    assert shared["version_no"] == 1 and shared["show_contact"] is False and shared["url_path"] == f"/api/v1/public/resumes/{shared['token']}" and len(shared["token"]) >= 30
    public = await client.get(shared["url_path"])
    assert public.status_code == 200 and public.headers["x-robots-tag"] == "noindex, nofollow"
    body = public.json()
    assert body["resume"]["basics"]["name"] == "Asha Rao" and "email" not in body["resume"]["basics"] and "phone" not in body["resume"]["basics"]
    assert body["document"]["personal"]["email"] is None and "asha@example.com" not in public.text and "98765" not in public.text
    who.student()
    await client.delete(f"{API}/profile/items/{ids['job']}")
    await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": 0, "title": "Edited later"})
    assert "Acme Labs" in (await client.get(shared["url_path"])).text  # edits after sharing do not change what was sent
    pdf = await client.get(f"{shared['url_path']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and pdf.headers["x-robots-tag"] == "noindex, nofollow"
    async with sessionmaker() as db:
        assert (await db.execute(select(Resume.share_views))).scalar_one() == 3
    events = [e["action"] for e in await outbox(sessionmaker, "resume.updated")]
    assert events == ["version_saved", "shared"]


async def test_show_contact_and_replacing_or_revoking_a_link(client, who, send_event):
    _, rid = await ready_student(client, who, send_event)
    first = (await client.post(f"{API}/resumes/{rid}/share", json={"show_contact": True, "expires_in_days": 5})).json()["share"]
    assert "asha@example.com" in (await client.get(first["url_path"])).text
    second = (await client.post(f"{API}/resumes/{rid}/share", json={"version_no": 1})).json()["share"]
    assert second["token"] != first["token"] and (await client.get(first["url_path"])).status_code == 404  # sharing again kills the old link
    assert (await client.get(second["url_path"])).status_code == 200
    assert (await client.delete(f"{API}/resumes/{rid}/share")).status_code == 204
    revoked = await client.get(second["url_path"])
    assert revoked.status_code == 404 and revoked.json()["code"] == "SHARE_NOT_FOUND"
    assert (await client.delete(f"{API}/resumes/{rid}/share")).status_code == 204  # revoking twice is fine
    assert (await client.post(f"{API}/resumes/{rid}/share", json={"version_no": 42})).status_code == 404
    assert (await client.get(f"{API}/public/resumes/not-a-real-token")).status_code == 404


async def test_expired_and_deleted_links_are_indistinguishable_from_unknown_ones(client, who, send_event, sessionmaker, settings):
    _, rid = await ready_student(client, who, send_event)
    link = (await client.post(f"{API}/resumes/{rid}/share", json={"expires_in_days": 1})).json()["share"]["url_path"]
    async with sessionmaker() as db:
        await db.execute(update(Resume).values(share_expires_at=utcnow() - timedelta(minutes=1)))
        await db.commit()
    expired = await client.get(link)
    unknown = await client.get(f"{API}/public/resumes/zzzz")
    assert expired.status_code == unknown.status_code == 404 and expired.json()["code"] == unknown.json()["code"]
    assert await housekeeping_once(sessionmaker, settings) == (0, 1)  # the housekeeping removes the dead token
    relink = (await client.post(f"{API}/resumes/{rid}/share", json={})).json()["share"]["url_path"]
    assert (await client.get(relink)).status_code == 200
    await client.delete(f"{API}/resumes/{rid}")
    assert (await client.get(relink)).status_code == 404  # deleting the resume kills its link


async def test_public_pages_are_rate_limited_per_address(client, app, settings):
    from app.core.config import get_settings
    from tests.conftest import _settings

    limited = _settings(RATE_LIMIT_ENABLED=True, PUBLIC_RATE_LIMIT_PER_IP_PER_MINUTE=3)
    app.dependency_overrides[get_settings] = lambda: limited
    codes = [(await client.get(f"{API}/public/resumes/anything")).status_code for _ in range(5)]
    assert codes == [404, 404, 404, 429, 429] and settings.RATE_LIMIT_ENABLED is False
