"""Screening: a score and reasons for a recruiter, from what an applicant has shown (docs/PRODUCT.md §5.7).

Two parts. The **rules** (always available, free, explainable) turn the match score into a screening score and add red flags a person
should look at. The **model** (when ai-gateway is reachable) gives its own score and reasons; the two are averaged. Either way the
result is a *recommendation* — shortlist, review or reject — that no code path acts on: only a person moves an application, and only
a person confirms a rejection.

Protected attributes are kept out by construction: ``anonymised_input`` builds the only text a model ever sees from the candidate's
facts and the resume's own bullets, with no name, email, phone, link, photo, date of birth, gender, institution or dates.
"""

import hashlib
import json
import re
from typing import Any

from app.matching.model import Candidate, JobSpec

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_BULLET_SECTIONS = {"experience", "projects", "achievements"}
_MAX_BULLETS = 12


def scrub(text: str) -> str:
    """Remove what could identify a person: emails, links, phone numbers, and years (which give away age)."""
    return _YEAR.sub("[year]", _PHONE.sub("[phone]", _URL.sub("[link]", _EMAIL.sub("[email]", text)))).strip()


def resume_bullets(document: dict[str, Any]) -> list[str]:
    """The work described in a resume snapshot: headings and bullets of experience, projects and achievements, scrubbed."""
    out: list[str] = []
    for section in document.get("sections", []):
        if section.get("key") not in _BULLET_SECTIONS:
            continue
        for entry in section.get("entries", []):
            head = scrub(" ".join(x for x in (entry.get("heading"), entry.get("subheading")) if x))
            for bullet in entry.get("bullets", []):
                out.append(scrub(f"{head}: {bullet}" if head else bullet))
    return out[:_MAX_BULLETS]


def red_flags(job: JobSpec, candidate: Candidate, document: dict[str, Any], *, matched_required: int, total_required: int) -> list[str]:
    """Things a person should look at. Each says what the rule saw, not what to conclude."""
    flags: list[str] = []
    if total_required and matched_required * 2 < total_required:
        flags.append(f"Matches only {matched_required} of {total_required} required skills")
    if job.experience_min_months and candidate.experience_months * 2 < job.experience_min_months:
        flags.append("Experience is well below what the job asks for")
    sections = {s.get("key") for s in document.get("sections", [])}
    if not sections & {"experience", "projects"}:
        flags.append("The resume has no experience or projects")
    if not candidate.certificate_course_ids and not candidate.scores:
        flags.append("Nothing on the profile is verified by the platform")
    return flags


def screening_score(match_score: int, flags: list[str]) -> int:
    """The rule-based fit: the match score, less 8 for each red flag."""
    return max(0, min(100, match_score - 8 * len(flags)))


def recommend(score: int, *, shortlist_at: int, reject_below: int) -> str:
    if score >= shortlist_at:
        return "shortlist"
    if score < reject_below:
        return "reject"
    return "review"


def anonymised_input(job: JobSpec, candidate: Candidate, courses: dict[int, str], document: dict[str, Any], match_explanation: list[str]) -> dict[str, Any]:
    """Everything a model is told about a job and an applicant."""
    return {
        "job": {
            "title": job.title, "required_skills": list(job.required_skills), "preferred_skills": list(job.preferred_skills), "experience_min_months": job.experience_min_months,
            "employment_type": job.employment_type, "description": scrub(job.description)[:1500],
        },
        "applicant": {
            "skills": list(candidate.skills), "technologies": list(candidate.technologies), "job_titles": list(candidate.job_titles), "experience_months": candidate.experience_months,
            "education": [scrub(e) for e in candidate.education],
            "certificates": sorted(courses.get(c, "a course") for c in candidate.certificate_course_ids),
            "assessment_scores": [{"course": courses.get(c, "a course"), "percent": p} for c, p in sorted(candidate.scores.items())],
            "work_described": resume_bullets(document),
        },
        "rule_based_match": match_explanation,
    }


def digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def user_message(payload: dict[str, Any]) -> str:
    return "JOB:\n" + json.dumps(payload["job"], ensure_ascii=False) + "\n\nAPPLICANT:\n" + json.dumps(payload["applicant"], ensure_ascii=False)


def parse_ai(text: str) -> dict[str, Any] | None:
    """The model's JSON answer, checked. ``None`` when it is not in the expected shape (the rules' result then stands alone)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except ValueError:
        return None
    score = data.get("score")
    if isinstance(score, bool) or not isinstance(score, int | float) or not 0 <= score <= 100:
        return None
    reasons = [str(r)[:200] for r in data.get("reasons", []) if isinstance(r, str)][:4]
    flags = [str(r)[:200] for r in data.get("red_flags", []) if isinstance(r, str)][:3]
    return {"score": round(score), "reasons": reasons, "red_flags": flags}
