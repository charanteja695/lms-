from tests.conftest import COURSE, passed_payload

BODY = "Awarded to\n{student_name}\nfor completing\n{course_title}\n({grade})"


async def create(client, who, **fields) -> dict:
    who.author()
    response = await client.post("/api/v1/certificate-templates", json={"name": "MERN certificate", "course_id": str(COURSE), **fields})
    assert response.status_code == 201, response.text
    return response.json()["template"]


async def activate(client, who, template_id: str) -> dict:
    who.reviewer()
    response = await client.post(f"/api/v1/certificate-templates/{template_id}/activate")
    assert response.status_code == 200, response.text
    return response.json()["template"]


async def first_certificate(client, who) -> dict:
    who.student()
    return (await client.get("/api/v1/certificates")).json()["certificates"][0]


async def test_a_template_starts_as_a_draft_with_sensible_defaults(client, who):
    template = await create(client, who)
    assert template["status"] == "draft" and template["title_text"] == "Certificate of Completion"
    assert [b["label"] for b in template["grade_bands"]] == ["Distinction", "Merit", "Pass"]
    assert "{student_name}" in template["body_text"] and template["accent_color"] == "#1F4E79"


async def test_placeholders_colours_and_bands_are_validated(client, who):
    who.author()
    bad_placeholder = await client.post("/api/v1/certificate-templates", json={"name": "T", "body_text": "Hello {password}"})
    assert bad_placeholder.status_code == 422 and bad_placeholder.json()["details"][0]["code"] == "INVALID_PLACEHOLDER"
    assert (await client.post("/api/v1/certificate-templates", json={"name": "T", "accent_color": "blue"})).status_code == 422
    no_floor = await client.post("/api/v1/certificate-templates", json={"name": "T", "grade_bands": [{"min_percent": 50, "label": "Pass"}]})
    assert no_floor.status_code == 422 and no_floor.json()["details"][0]["field"] == "grade_bands"
    unknown = await client.post("/api/v1/certificate-templates", json={"name": "T", "logo": "x"})
    assert unknown.status_code == 422


async def test_authors_write_reviewers_activate_and_students_see_nothing(client, who):
    template = await create(client, who)
    who.author()
    denied = await client.post(f"/api/v1/certificate-templates/{template['template_id']}/activate")
    assert denied.status_code == 403  # writing a template is not publishing it
    who.reviewer()
    assert (await client.post("/api/v1/certificate-templates", json={"name": "T"})).status_code == 403
    assert (await client.get(f"/api/v1/certificate-templates/{template['template_id']}")).status_code == 200
    who.student()
    assert (await client.get("/api/v1/certificate-templates")).status_code == 403
    assert (await client.get(f"/api/v1/certificate-templates/{template['template_id']}/preview")).status_code == 403


async def test_only_a_draft_can_be_edited(client, who):
    template = await create(client, who)
    who.author()
    assert (await client.patch(f"/api/v1/certificate-templates/{template['template_id']}", json={"title_text": "Diploma"})).json()["template"]["title_text"] == "Diploma"
    await activate(client, who, template["template_id"])
    who.author()
    refused = await client.patch(f"/api/v1/certificate-templates/{template['template_id']}", json={"title_text": "Other"})
    assert refused.status_code == 409 and refused.json()["code"] == "TEMPLATE_NOT_DRAFT"


async def test_activating_replaces_the_active_template_for_that_course_only(client, who):
    first = await create(client, who, name="First")
    other_course = await create(client, who, name="Other course", course_id="1755000000001999")
    await activate(client, who, first["template_id"])
    await activate(client, who, other_course["template_id"])
    second = await create(client, who, name="Second")
    await activate(client, who, second["template_id"])
    who.reviewer()
    statuses = {t["name"]: t["status"] for t in (await client.get("/api/v1/certificate-templates")).json()["templates"]}
    assert statuses == {"First": "archived", "Second": "active", "Other course": "active"}
    assert (await client.post(f"/api/v1/certificate-templates/{first['template_id']}/activate")).json()["code"] == "TEMPLATE_ARCHIVED"
    only_active = (await client.get("/api/v1/certificate-templates", params={"status": "active", "course_id": str(COURSE)})).json()["templates"]
    assert [t["name"] for t in only_active] == ["Second"]


async def test_a_course_template_beats_the_platform_default_and_both_beat_the_built_in_one(client, who, send_event, directory, sessionmaker):
    from sqlalchemy import select

    from app.models.certificate import Certificate

    await directory()
    await send_event("course.passed", passed_payload(attempt=1755000000009101))  # no template at all: the built-in one
    default = await create(client, who, name="Platform default", course_id=None, title_text="Platform Certificate")
    await activate(client, who, default["template_id"])
    await send_event("course.passed", passed_payload(student=1755000000007102, attempt=1755000000009102))
    course = await create(client, who, name="MERN", title_text="MERN Achievement", grade_bands=[{"min_percent": 0, "label": "Completed"}, {"min_percent": 90, "label": "Gold"}])
    await activate(client, who, course["template_id"])
    await send_event("course.passed", passed_payload(student=1755000000007103, attempt=1755000000009103))

    async with sessionmaker() as db:
        rows = (await db.execute(select(Certificate).order_by(Certificate.attempt_id))).scalars().all()
    assert [r.template_snapshot["title_text"] for r in rows] == ["Certificate of Completion", "Platform Certificate", "MERN Achievement"]
    assert [r.grade_label for r in rows] == ["Distinction", "Distinction", "Gold"]  # the course's own bands


async def test_changing_a_template_never_changes_a_certificate_already_issued(client, who, send_event, directory, sessionmaker, render):
    from sqlalchemy import select

    from app.models.certificate import Certificate

    template = await create(client, who, title_text="Original Title")
    await activate(client, who, template["template_id"])
    await directory()
    await send_event("course.passed", passed_payload())
    newer = await create(client, who, title_text="Redesigned Title")
    await activate(client, who, newer["template_id"])
    async with sessionmaker() as db:
        assert (await db.execute(select(Certificate.template_snapshot))).scalar_one()["title_text"] == "Original Title"
    await render()  # rendered from the snapshot, whatever the template is now


async def test_a_preview_renders_a_sample_pdf(client, who):
    template = await create(client, who, body_text=BODY, signatories=[{"name": "Dr. R. Iyer", "title": "Dean"}])
    who.author()
    response = await client.get(f"/api/v1/certificate-templates/{template['template_id']}/preview")
    assert response.status_code == 200 and response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
