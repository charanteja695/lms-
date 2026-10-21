import io
import json
import zipfile

from tests.conftest import STUDENT_2
from tests.integration.test_resumes import ready_student

API = "/api/v1"

OLD_RESUME = """Ravi Kumar
Hyderabad | +91 90000 11111
Senior Java Developer with 9 years building payment systems.
EXPERIENCE
Lead Engineer, Paytrail Systems, Jan 2019 - Present
- Led a team of 6 engineers building a payments API in Java and Spring Boot
- Cut settlement time from 2 days to 4 hours
EDUCATION
B.Tech Computer Science, JNTU Hyderabad, 2011 - 2015
SKILLS
Java, Spring Boot, Kafka
"""


def _docx(text: str) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.splitlines())
    xml = f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def _reading(*, invented: bool = False) -> str:
    items = [
        {"kind": "experience", "data": {"company": "Paytrail Systems", "title": "Lead Engineer", "start_date": "2019-01", "current": True,
                                         "bullets": ["Led a team of 6 engineers building a payments API in Java and Spring Boot", "Cut settlement time from 2 days to 4 hours"]}},
        {"kind": "education", "data": {"institution": "JNTU Hyderabad", "degree": "B.Tech", "field_of_study": "Computer Science", "start_date": "2011-01", "end_date": "2015-12"}},
        {"kind": "skill", "data": {"name": "Java"}},
        {"kind": "skill", "data": {"name": "Kafka"}},
        {"kind": "skill", "data": {"name": "Kubernetes" if invented else "Spring Boot"}},  # not in the file -> dropped
        {"kind": "certificate", "data": {"name": "Made up"}},  # a verified kind can never be imported
        {"kind": "project", "data": {"technologies": []}},  # no name -> invalid
    ]
    return "```json\n" + json.dumps({"headline": "Senior Java Developer", "summary": None, "phone": "+91 90000 11111", "location": "Hyderabad", "items": items}) + "\n```"


# ---------------------------------------------------------------- experience level
async def test_options_come_from_the_server(client, who, settings):
    who.student()
    await client.patch(f"{API}/profile", json={"target_roles": ["Platform Engineer", "Java Developer"]})
    options = (await client.get(f"{API}/resume-options")).json()
    assert [o["key"] for o in options["experience_levels"]] == ["fresher", "junior", "mid", "senior"] and all(o["note"] for o in options["experience_levels"])
    assert [o["key"] for o in options["start_options"]] == ["profile", "import", "linkedin", "blank"]
    assert [t["key"] for t in options["ai_tones"]] == ["professional", "warm", "concise"]
    assert options["share_expiry_days"] == [7, 30, 90] and options["share_default_days"] == settings.SHARE_DEFAULT_DAYS
    roles = options["role_suggestions"]
    assert roles[:2] == ["Platform Engineer", "Java Developer"] and roles.count("Java Developer") == 1  # own roles first, no duplicate
    assert options["max_resumes"] == settings.MAX_RESUMES_PER_USER and options["max_import_bytes"] == settings.MAX_IMPORT_BYTES


async def test_level_sets_the_order_and_changing_it_reorders(client, who, send_event):
    await ready_student(client, who, send_event)
    created = (await client.post(f"{API}/resumes", json={"title": "Senior", "experience_level": "senior"})).json()["resume"]
    assert created["experience_level"] == "senior"
    rid = created["resume_id"]
    detail = (await client.get(f"{API}/resumes/{rid}")).json()
    keys = [s["key"] for s in detail["draft"]["sections"]]
    assert keys[0] == "experience" and keys.index("education") > keys.index("achievements")
    listed = (await client.get(f"{API}/resumes")).json()["resumes"]
    assert all(isinstance(r["ats_score"], int) for r in listed) and detail["ats"]["score"] in [r["ats_score"] for r in listed]
    hidden = [{**s, "visible": s["key"] != "projects"} for s in detail["draft"]["sections"]]
    await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": 0, "draft": {**detail["draft"], "sections": hidden}})
    changed = await client.patch(f"{API}/resumes/{rid}", json={"expected_revision": 1, "experience_level": "fresher"})
    assert changed.status_code == 200 and changed.json()["resume"]["experience_level"] == "fresher"
    after = (await client.get(f"{API}/resumes/{rid}")).json()["draft"]["sections"]
    assert [s["key"] for s in after][:3] == ["skills", "projects", "experience"]
    assert {s["key"]: s["visible"] for s in after}["projects"] is False  # reordering never shows or hides anything


async def test_score_has_a_path_to_100(client, who, send_event):
    _, rid = await ready_student(client, who, send_event)
    ats = (await client.get(f"{API}/resumes/{rid}")).json()["ats"]
    path = ats["path_to_100"]
    assert path and all(p["gain"] > 0 for p in path) and path == sorted(path, key=lambda p: -p["gain"])
    assert round(ats["score"] + sum(p["gain"] for p in path)) in (99, 100, 101)  # rounding of each part


# ---------------------------------------------------------------- import
async def test_import_reads_a_docx_and_keeps_only_checked_entries(client, who, gateway):
    who.student()
    gateway.reply(_reading(invented=True))
    response = await client.post(f"{API}/profile/import", files={"file": ("old.docx", _docx(OLD_RESUME), "application/octet-stream")})
    assert response.status_code == 200, response.text
    body = response.json()
    assert [(i["kind"], i["label"]) for i in body["items"]] == [
        ("experience", "Lead Engineer · Paytrail Systems"), ("education", "B.Tech · JNTU Hyderabad"), ("skill", "Java"), ("skill", "Kafka")
    ]
    assert body["skipped"] == 3 and body["profile"]["headline"] == "Senior Java Developer" and body["profile"]["location"] == "Hyderabad"
    call = gateway.requests[0]
    assert call["prompt_key"] == "career.import" and "Paytrail Systems" in call["messages"][0]["content"]
    assert (await client.get(f"{API}/profile")).json()["items"] == []  # nothing saved by an import


async def test_import_rejects_bad_files(client, who, gateway, settings):
    who.student()
    assert (await client.post(f"{API}/profile/import", files={"file": ("x.png", b"\x89PNG\r\n\x1a\n\xff\xfe", "image/png")})).json()["code"] == "UNSUPPORTED_FILE"
    assert (await client.post(f"{API}/profile/import", files={"file": ("x.txt", b"too short", "text/plain")})).json()["code"] == "UNREADABLE_FILE"
    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w") as archive:
        archive.writestr("word/document.xml", '<!DOCTYPE d [<!ENTITY a "aaaa">]><d>&a;</d>')
    assert (await client.post(f"{API}/profile/import", files={"file": ("x.docx", bomb.getvalue(), "application/octet-stream")})).json()["code"] == "UNREADABLE_FILE"
    big = await client.post(f"{API}/profile/import", files={"file": ("x.txt", b"a" * (settings.MAX_IMPORT_BYTES + 1), "text/plain")})
    assert big.status_code == 413 and big.json()["code"] == "FILE_TOO_LARGE"
    assert gateway.requests == []


async def test_bulk_add_is_all_or_nothing(client, who):
    who.student()
    good = {"kind": "skill", "data": {"name": "Java"}}
    bad = await client.post(f"{API}/profile/items/bulk", json={"items": [good, {"kind": "experience", "data": {"company": "X"}}]})
    assert bad.status_code == 422 and any(d["field"].startswith("items.1.") for d in bad.json()["details"])
    assert (await client.get(f"{API}/profile")).json()["items"] == []
    verified = await client.post(f"{API}/profile/items/bulk", json={"items": [{"kind": "certificate", "data": {}}]})
    assert verified.status_code == 422
    added = await client.post(f"{API}/profile/items/bulk", json={"items": [good, {"kind": "skill", "data": {"name": "Kafka"}}]})
    assert added.status_code == 201 and [i["data"]["name"] for i in added.json()["items"]] == ["Java", "Kafka"]
    assert [i["position"] for i in added.json()["items"]] == [0, 1]
    who.student(STUDENT_2)
    assert (await client.get(f"{API}/profile")).json()["items"] == []


async def test_import_reads_a_pdf(client, who, gateway):
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for row, line in enumerate(OLD_RESUME.splitlines()):
        pdf.drawString(40, 800 - 14 * row, line)
    pdf.save()
    who.student()
    gateway.reply(_reading())
    response = await client.post(f"{API}/profile/import", files={"file": ("linkedin.pdf", buffer.getvalue(), "application/pdf")})
    assert response.status_code == 200, response.text
    assert "Paytrail Systems" in gateway.requests[0]["messages"][0]["content"]
    assert ("skill", "Spring Boot") in [(i["kind"], i["label"]) for i in response.json()["items"]]
