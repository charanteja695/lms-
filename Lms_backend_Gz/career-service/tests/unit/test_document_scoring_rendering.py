import json
from types import SimpleNamespace

from app.ats.scoring import score_document
from app.rendering.jsonresume import to_json_resume
from app.rendering.pdf import render_pdf
from app.rendering.templates import DEFAULT_TEMPLATES
from app.resume.document import build_document, date_range, default_draft, document_text, month_label
from app.services.profile_service import ItemView
from tests.conftest import JOB, PROJECT, SCHOOL


def view(item_id: int, kind: str, data: dict, *, verified: bool = False, derived: dict | None = None) -> ItemView:
    item = SimpleNamespace(public_id=item_id, kind=kind, verified=verified, position=0, active=True)
    return ItemView(item=item, data=data, derived=derived or {})  # type: ignore[arg-type]


VIEWS = [
    view(1, "education", SCHOOL), view(2, "experience", JOB), view(3, "project", PROJECT), view(4, "skill", {"name": "Python"}), view(5, "skill", {"name": "SQL"}),
    view(6, "certificate", {"certificate_id": "9", "course_id": "7", "grade": "A", "issued_at": "2026-09-01T10:00:00Z", "verification_url": "https://lms.example/verify/9"}, verified=True, derived={"course_title": "Python Programming"}),
    view(7, "skill_score", {"course_id": "7", "best_percent": 91.5, "attempts": 2}, verified=True, derived={"course_title": "Python Programming", "percentile": 84, "cohort_size": 240}),
    view(8, "course", {"course_id": "7", "completed_at": "2026-08-30"}, verified=True, derived={"course_title": "Python Programming"}),
]


def doc(draft=None, **kw):
    args = {"name": "Asha Rao", "email": "asha@example.com", "phone": "+91 98765 43210", "location": "Chennai", "headline": "Backend developer", "links": [{"label": "GitHub", "url": "https://github.com/asha"}], "profile_summary": None, "views": VIEWS}
    args.update(kw)
    return build_document(draft or default_draft(VIEWS), **args)


def test_dates():
    assert month_label("2024-06") == "Jun 2024" and month_label("2026-09-01T10:00:00Z") == "Sep 2026" and month_label("nonsense") is None and month_label(None) is None
    assert date_range("2024-06", "2025-01") == "Jun 2024 – Jan 2025" and date_range("2024-06", None, True) == "Jun 2024 – Present" and date_range(None, None) is None


def test_default_draft_orders_sections_and_hides_redundant_courses():
    draft = default_draft(VIEWS)
    assert [s["key"] for s in draft["sections"]] == ["skills", "projects", "experience", "education", "certificates", "skill_scores", "courses"]
    assert {s["key"]: s["visible"] for s in draft["sections"]}["courses"] is False
    assert default_draft([])["sections"] == []


def test_document_marks_verified_and_formats_entries():
    document = doc()
    assert document["personal"]["name_verified"] is True
    sections = {s["key"]: s for s in document["sections"]}
    assert "courses" not in sections  # hidden by default
    cert = sections["certificates"]["entries"][0]
    assert cert["verified"] is True and cert["label"] == "Verified" and cert["heading"] == "Python Programming — Certificate"
    assert cert["bullets"] == ["Grade: A", "Verify: https://lms.example/verify/9"] and cert["dates"] == "Sep 2026"
    score = sections["skill_scores"]["entries"][0]
    assert score["bullets"] == ["Best score 91.5% — 84th percentile among 240 students"]
    job = sections["experience"]["entries"][0]
    assert job["label"] == "Self-declared" and job["heading"] == "Software Intern" and job["subheading"] == "Acme Labs" and job["dates"] == "May 2025 – Jul 2025"
    assert sections["education"]["entries"][0]["bullets"][0] == "Grade: 8.4 CGPA"


def test_percentile_is_left_out_when_unknown():
    lonely = [view(7, "skill_score", {"course_id": "7", "best_percent": 91.5}, verified=True, derived={"course_title": "X", "percentile": None, "cohort_size": 4})]
    document = doc({"summary": {}, "personal": {}, "sections": [{"key": "skill_scores", "visible": True, "items": [{"item_id": "7"}]}]}, views=lonely)
    assert document["sections"][0]["entries"][0]["bullets"] == ["Best score 91.5%"]


def test_bullet_overrides_apply_to_own_entries_only():
    draft = {
        "summary": {}, "personal": {},
        "sections": [
            {"key": "experience", "visible": True, "items": [{"item_id": "2", "bullets": ["Reworded for this job"]}]},
            {"key": "certificates", "visible": True, "items": [{"item_id": "6", "bullets": ["Grade: A+++ (a lie)"]}]},
        ],
    }
    sections = {s["key"]: s for s in doc(draft)["sections"]}
    assert sections["experience"]["entries"][0]["bullets"] == ["Reworded for this job"]
    assert "A+++" not in str(sections["certificates"])  # a verified item is never reworded


def test_missing_wrong_section_and_hidden_items_are_dropped():
    draft = {
        "summary": {"visible": False}, "personal": {"show_phone": False, "show_location": False, "show_links": False},
        "sections": [{"key": "skills", "visible": True, "items": [{"item_id": "999"}, {"item_id": "2"}, {"item_id": "4"}]}, {"key": "projects", "visible": False, "items": [{"item_id": "3"}]}],
    }
    document = doc(draft, profile_summary="About me")
    assert [e["heading"] for e in document["sections"][0]["entries"]] == ["Python"] and len(document["sections"]) == 1
    assert document["summary"] is None
    assert document["personal"]["phone"] is None and document["personal"]["location"] is None and document["personal"]["links"] == []


def test_summary_falls_back_to_the_profile():
    assert doc(profile_summary="About me")["summary"] == "About me"
    assert doc({"summary": {"text": "Custom", "visible": True}, "personal": {}, "sections": []}, profile_summary="About me")["summary"] == "Custom"


def test_document_text_contains_what_a_reader_sees():
    text = document_text(doc())
    assert "Asha Rao" in text and "Acme Labs" in text and "REST API" in text and "Education" in text


# ---------------------------------------------------------------- ATS score
def test_score_is_deterministic_and_explains_itself():
    a, b = score_document(doc(), template_ats_safe=True), score_document(doc(), template_ats_safe=True)
    assert a.as_dict() == b.as_dict() and 0 <= a.score <= 100
    assert {c.key for c in a.components} == {"contact", "sections", "bullets", "summary", "length", "template"}
    codes = {f.code for f in a.fixes}
    assert "NO_SUMMARY" in codes and "NO_ACTION_VERB" in codes  # "worked on tests" does not start with an action verb
    severities = [f.severity for f in a.fixes]
    assert severities == sorted(severities, key={"high": 0, "medium": 1, "low": 2}.get)


def test_an_empty_resume_scores_low_and_says_why():
    empty = build_document({"summary": {}, "personal": {}, "sections": []}, name="A B", email=None, phone=None, location=None, headline=None, links=[], profile_summary=None, views=[])
    report = score_document(empty, template_ats_safe=True)
    assert report.score < 40
    assert {"NO_EMAIL", "NO_EDUCATION", "NO_EXPERIENCE_OR_PROJECTS", "NO_SKILLS", "NO_BULLETS", "NO_SUMMARY", "LENGTH"} <= {f.code for f in report.fixes}


def test_a_better_resume_scores_higher():
    weak = score_document(doc({"summary": {}, "personal": {}, "sections": [{"key": "experience", "visible": True, "items": [{"item_id": "2", "bullets": ["worked on stuff", "responsible for things"]}]}]}), template_ats_safe=True)
    strong = score_document(doc({**default_draft(VIEWS), "summary": {"text": "Backend developer who builds REST APIs in Python and FastAPI, with an internship shipping services used by thousands of users and a certified Python course.", "visible": True}}), template_ats_safe=True)
    assert strong.score > weak.score


def test_non_ats_template_and_nonstandard_headings_cost_points():
    document = doc()
    safe = score_document(document, template_ats_safe=True)
    unsafe = score_document(document, template_ats_safe=False)
    assert unsafe.score < safe.score and "TEMPLATE_NOT_ATS_SAFE" in {f.code for f in unsafe.fixes}
    odd = doc({**default_draft(VIEWS), "sections": [{**s, "title": "My Journey" if s["key"] == "experience" else s["title"]} for s in default_draft(VIEWS)["sections"]]})
    assert "NONSTANDARD_HEADING" in {f.code for f in score_document(odd, template_ats_safe=True).fixes}


def test_keyword_match_joins_the_score_when_a_job_description_is_given():
    jd = "Backend developer: Python, FastAPI, PostgreSQL, Docker, Kubernetes, Kubernetes, Kubernetes"
    without = score_document(doc(), template_ats_safe=True)
    with_jd = score_document(doc(), template_ats_safe=True, job_description=jd)
    assert "keywords" in {c.key for c in with_jd.components} and "keywords" not in {c.key for c in without.components}
    missing = [f for f in with_jd.fixes if f.code == "MISSING_KEYWORDS"]
    assert missing and "kubernetes" in missing[0].message.lower()
    assert {k.term: k.present for k in with_jd.keywords}["python"] is True


# ---------------------------------------------------------------- exports
def test_pdf_renders_for_every_template_and_counts_lost_characters():
    document = doc()
    for spec in DEFAULT_TEMPLATES.values():
        pdf, lost = render_pdf(document, spec["config"], title="My resume")
        assert pdf.startswith(b"%PDF") and len(pdf) > 1500 and lost == 0
    devanagari = doc(name="आशा Rao")
    _, lost = render_pdf(devanagari, DEFAULT_TEMPLATES["classic"]["config"], title="r")
    assert lost == 3


def test_json_resume_follows_the_schema_shape():
    document = doc()
    raw = {str(v.item.public_id): v.data for v in VIEWS}
    resume = to_json_resume(document, raw_items=raw)
    assert resume["basics"]["name"] == "Asha Rao" and resume["basics"]["email"] == "asha@example.com" and resume["basics"]["profiles"][0]["network"] == "GitHub"
    assert resume["work"][0] == {"name": "Acme Labs", "position": "Software Intern", "startDate": "2025-05", "highlights": JOB["bullets"], "endDate": "2025-07", "location": "Chennai"}
    assert resume["education"][0]["institution"] == "Anna University" and resume["education"][0]["score"] == "8.4 CGPA"
    assert resume["projects"][0]["keywords"] == ["Python", "FastAPI", "PostgreSQL"] and resume["skills"] == [{"name": "Python", "keywords": []}, {"name": "SQL", "keywords": []}]
    assert resume["certificates"][0]["url"] == "https://lms.example/verify/9"
    assert {i["kind"] for i in resume["x-lms"]["verified_items"]} == {"certificate", "skill_score"}
    json.dumps(resume)  # serialisable


# ---------------------------------------------------------------- facts carried to job-portal-service
def test_matching_facts_carry_skills_and_experience_but_no_identity():
    from datetime import date

    from app.profile_facts import matching_facts

    def row(kind, data, *, active=True):
        return SimpleNamespace(kind=kind, data=data, active=active)

    profile = SimpleNamespace(location="Chennai", target_roles=["Backend Developer"], headline="Aspiring backend developer")
    items = [
        row("skill", {"name": "Python"}), row("skill", {"name": "python"}), row("skill", {"name": "SQL"}), row("skill", {"name": "Old"}, active=False),
        row("project", {"technologies": ["FastAPI", "Python"]}), row("experience", {"title": "Intern", "start_date": "2025-05", "end_date": "2025-07"}),
        row("experience", {"title": "Developer", "start_date": "2025-09", "current": True}),
        row("education", {"degree": "B.Tech", "field_of_study": "CS", "start_date": "2022-08", "end_date": "2026-05", "institution": "Anna University"}),
        row("certificate", {"course_id": "7"}), row("skill_score", {"course_id": "7", "best_percent": 91.5}),
    ]
    facts = matching_facts(profile, items, today=date(2026, 1, 15))
    assert sorted(s.lower() for s in facts["skills"]) == ["python", "python", "sql"]  # names are kept as written; matching lower-cases them
    assert facts["technologies"] == ["FastAPI", "Python"] and facts["experience_months"] == 3 + 5 and facts["graduation_year"] == 2026
    assert facts["certificates"] == ["7"] and facts["scores"] == [{"course_id": "7", "best_percent": 91.5}] and facts["job_titles"] == ["Intern", "Developer"]
    assert "Anna University" not in str(facts) and "Old" not in str(facts)  # no institution, no inactive items
