import pytest

from app.core.exceptions import ValidationFailedError
from app.render.layout import (
    DEFAULT_GRADE_BANDS,
    DEFAULT_TEMPLATE,
    fill,
    grade_for,
    validate_bands,
    validate_color,
    validate_text_placeholders,
)
from app.render.pdf import CertificateData, render_pdf


def data(**overrides) -> CertificateData:
    values = {
        "certificate_id": "360471859873173362",
        "student_name": "Aarav Reddy",
        "course_title": "Full Stack Development with MERN",
        "institution_name": "Springfield High",
        "completion_date": "21 September 2026",
        "score_percent": "91.5",
        "grade": "Distinction",
        "issuer": "LMS",
        "verification_url": "https://lms.example/verify/abc123",
        "verification_code": "abc123",
        "template": DEFAULT_TEMPLATE,
    }
    values.update(overrides)
    return CertificateData(**values)


def test_the_pdf_is_a_real_pdf_and_identical_for_identical_input():
    first, second = render_pdf(data()), render_pdf(data())
    assert first.startswith(b"%PDF-") and first.rstrip().endswith(b"%%EOF") and len(first) > 2_000
    assert first == second  # regenerating a certificate produces the same file


def test_the_pdf_changes_with_the_content_and_supports_signatories():
    template = {**DEFAULT_TEMPLATE, "signatories": [{"name": "Dr. R. Iyer", "title": "Dean"}, {"name": "S. Mehta", "title": "Director"}]}
    assert render_pdf(data(template=template)) != render_pdf(data())
    assert render_pdf(data(student_name="Someone Else")) != render_pdf(data())


def test_a_long_name_and_title_still_render():
    assert render_pdf(data(student_name="Venkata Satya Narayana Raju Kothapalli-Subramaniam", course_title="A" * 150)).startswith(b"%PDF-")


def test_grade_bands_map_a_score_to_a_label():
    assert [grade_for(p, DEFAULT_GRADE_BANDS) for p in (100, 85, 84.99, 70, 69, 0)] == ["Distinction", "Distinction", "Merit", "Merit", "Pass", "Pass"]


def test_bands_must_cover_every_score_and_not_overlap():
    assert [b["label"] for b in validate_bands([{"min_percent": 0, "label": "Pass"}, {"min_percent": 90, "label": "Gold"}])] == ["Gold", "Pass"]
    with pytest.raises(ValidationFailedError):
        validate_bands([{"min_percent": 50, "label": "Pass"}])
    with pytest.raises(ValidationFailedError):
        validate_bands([{"min_percent": 0, "label": "A"}, {"min_percent": 0, "label": "B"}])


def test_only_known_placeholders_are_allowed():
    validate_text_placeholders("body_text", "{student_name} finished {course_title}")
    with pytest.raises(ValidationFailedError) as caught:
        validate_text_placeholders("body_text", "Hello {password}")
    assert caught.value.details[0]["code"] == "INVALID_PLACEHOLDER"
    with pytest.raises(ValidationFailedError):
        validate_text_placeholders("body_text", "Unbalanced {student_name")


def test_a_missing_grade_leaves_no_empty_brackets():
    assert fill("Scored {score_percent}% ({grade}).", {"score_percent": "80", "grade": ""}) == "Scored 80%."
    assert fill("Scored {score_percent}% ({grade}).", {"score_percent": "80", "grade": "Merit"}) == "Scored 80% (Merit)."


def test_colours_are_hex():
    assert validate_color("#1f4e79") == "#1F4E79"
    with pytest.raises(ValidationFailedError):
        validate_color("blue")
