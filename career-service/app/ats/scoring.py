"""The ATS score: how well an applicant tracking system will read a resume, with the fixes that raise it.

Computed by rules over the resolved document, so the same resume always scores the same and every point has a reason a
student can act on. It measures *parseability and content quality*, not whether a person will like the resume. Points:

  contact 10 · sections 15 · bullet quality 30 · summary 5 · length 10 · template 10 · keyword match 20 (only with a job description)

Without a job description the score is the share of the 80 points that apply, scaled to 100.
"""

from dataclasses import dataclass, field
from typing import Any

from app.ats.keywords import Keyword
from app.ats.keywords import coverage as keyword_coverage
from app.ats.language import check_text, is_quantified, starts_with_action_verb
from app.domain.enums import DEFAULT_TITLES
from app.resume.document import document_text

_STANDARD_TITLES = {t.lower() for t in DEFAULT_TITLES.values()} | {
    "work experience", "professional experience", "employment", "education", "academic background", "technical skills", "certifications", "certificates",
    "projects", "personal projects", "academic projects", "achievements", "awards", "courses", "summary", "profile", "professional summary", "objective",
}
_BULLET_KINDS = {"experience", "project", "achievement"}  # the entries whose bullets are the student's own words


@dataclass(slots=True)
class Component:
    key: str
    label: str
    points: float
    maximum: int
    detail: str


@dataclass(slots=True)
class Fix:
    code: str
    severity: str  # "high" | "medium" | "low"
    message: str
    section: str | None = None
    item_id: str | None = None


@dataclass(slots=True)
class AtsReport:
    score: int
    components: list[Component]
    fixes: list[Fix]
    keywords: list[Keyword] = field(default_factory=list)
    word_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score, "word_count": self.word_count,
            "components": [{"key": c.key, "label": c.label, "points": round(c.points, 1), "max": c.maximum, "detail": c.detail} for c in self.components],
            "fixes": [{"code": f.code, "severity": f.severity, "message": f.message, "section": f.section, "item_id": f.item_id} for f in self.fixes],
            "keywords": [{"term": k.term, "weight": k.weight, "present": k.present} for k in self.keywords],
        }


def _bullets(document: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(section key, item id, bullet) for the student's own words."""
    out: list[tuple[str, str, str]] = []
    for section in document["sections"]:
        for entry in section["entries"]:
            if entry["kind"] in _BULLET_KINDS:
                out.extend((section["key"], entry["item_id"], b) for b in entry["bullets"] if not b.startswith(("http://", "https://")))
    return out


def score_document(document: dict[str, Any], *, template_ats_safe: bool, job_description: str | None = None) -> AtsReport:
    personal, sections = document["personal"], document["sections"]
    keys = {s["key"] for s in sections}
    text = document_text(document)
    words = len(text.split())
    components: list[Component] = []
    fixes: list[Fix] = []

    # contact
    points = 0.0
    if personal.get("email"):
        points += 4
    else:
        fixes.append(Fix("NO_EMAIL", "high", "Add an email address: recruiters and ATS forms need one."))
    if personal.get("phone"):
        points += 3
    else:
        fixes.append(Fix("NO_PHONE", "medium", "Add a phone number to your profile (and keep it shown on this resume)."))
    if personal.get("location") or personal.get("links"):
        points += 3
    else:
        fixes.append(Fix("NO_LOCATION_OR_LINK", "low", "Add a city or a link (GitHub, LinkedIn, portfolio)."))
    components.append(Component("contact", "Contact details", points, 10, "email, phone, and a location or link"))

    # sections
    points = 0.0
    if "education" in keys:
        points += 5
    else:
        fixes.append(Fix("NO_EDUCATION", "high", "Add an Education section."))
    if keys & {"experience", "projects"}:
        points += 5
    else:
        fixes.append(Fix("NO_EXPERIENCE_OR_PROJECTS", "high", "Add Experience or Projects: it is what most recruiters read first."))
    if "skills" in keys:
        points += 5
    else:
        fixes.append(Fix("NO_SKILLS", "high", "Add a Skills section: ATS filters match on it."))
    odd = [s["title"] for s in sections if s["title"].lower() not in _STANDARD_TITLES]
    if odd:
        points = max(points - 2 * len(odd), 0)
        fixes.append(Fix("NONSTANDARD_HEADING", "medium", f"Rename {', '.join(repr(t) for t in odd)} to a standard heading (Experience, Education, Skills…); parsers look for those words."))
    components.append(Component("sections", "Standard sections", points, 15, "education, experience or projects, skills, with standard headings"))

    # bullets
    bullets = _bullets(document)
    if not bullets:
        components.append(Component("bullets", "Bullet quality", 0, 30, "no bullets under experience or projects"))
        fixes.append(Fix("NO_BULLETS", "high", "Describe what you did in short bullets under each experience or project."))
    else:
        verbs = sum(1 for _, _, b in bullets if starts_with_action_verb(b)) / len(bullets)
        quant = sum(1 for _, _, b in bullets if is_quantified(b)) / len(bullets)
        sized = sum(1 for _, _, b in bullets if 40 <= len(b) <= 220) / len(bullets)
        clean = sum(1 for _, _, b in bullets if not [i for i in check_text(b) if i.severity in {"error", "warning"}]) / len(bullets)
        components.append(Component("bullets", "Bullet quality", 10 * verbs + 10 * quant + 5 * sized + 5 * clean, 30, f"{len(bullets)} bullets: action verbs, numbers, length, wording"))
        for section, item_id, bullet in bullets:
            if not starts_with_action_verb(bullet):
                fixes.append(Fix("NO_ACTION_VERB", "medium", f"Start with an action verb: “{bullet[:60]}”", section, item_id))
            if not is_quantified(bullet):
                fixes.append(Fix("NOT_QUANTIFIED", "low", f"Add a number if you truthfully have one (how many, how much, how fast): “{bullet[:60]}”", section, item_id))
            if not 40 <= len(bullet) <= 220:
                fixes.append(Fix("BULLET_LENGTH", "low", f"Aim for one or two lines (40–220 characters): “{bullet[:60]}”", section, item_id))
            for issue in check_text(bullet):
                if issue.severity in {"error", "warning"}:
                    fixes.append(Fix(issue.code, "medium", issue.message, section, item_id))

    # summary
    summary = document.get("summary")
    if summary:
        n = len(summary.split())
        components.append(Component("summary", "Summary", 5 if 20 <= n <= 80 else 3, 5, f"{n} words"))
        if not 20 <= n <= 80:
            fixes.append(Fix("SUMMARY_LENGTH", "low", "Keep the summary to two or three sentences (20–80 words).", "summary"))
    else:
        components.append(Component("summary", "Summary", 0, 5, "none"))
        fixes.append(Fix("NO_SUMMARY", "low", "Add a two- or three-sentence summary aimed at the role."))

    # length
    if 250 <= words <= 800:
        length_points, note = 10, "a good length"
    elif 150 <= words < 250 or 800 < words <= 1000:
        length_points, note = 6, "a little short or long"
        fixes.append(Fix("LENGTH", "low", "Aim for 250–800 words: one page for a fresher, two at most."))
    else:
        length_points, note = 2, "too short or too long"
        fixes.append(Fix("LENGTH", "medium", "Aim for 250–800 words: one page for a fresher, two at most."))
    components.append(Component("length", "Length", length_points, 10, f"{words} words, {note}"))

    # template
    components.append(Component("template", "Layout", 10 if template_ats_safe else 4, 10, "single column, plain text" if template_ats_safe else "a layout parsers may misread"))
    if not template_ats_safe:
        fixes.append(Fix("TEMPLATE_NOT_ATS_SAFE", "high", "Switch to an ATS-safe template."))

    # keywords
    coverage: list[Keyword] = []
    total_max = 80
    if job_description and job_description.strip():
        coverage = keyword_coverage(job_description, text)
        weight = sum(k.weight for k in coverage) or 1
        matched = sum(k.weight for k in coverage if k.present)
        components.append(Component("keywords", "Keyword match", 20 * matched / weight, 20, f"{sum(k.present for k in coverage)} of {len(coverage)} key terms"))
        total_max = 100
        missing = [k.term for k in coverage if not k.present][:8]
        if missing:
            fixes.append(Fix("MISSING_KEYWORDS", "high", f"The job description stresses {', '.join(missing)}; add the ones that are true for you.", "keywords"))
    total = sum(c.points for c in components)
    order = {"high": 0, "medium": 1, "low": 2}
    fixes.sort(key=lambda f: order[f.severity])
    return AtsReport(score=round(100 * total / total_max), components=components, fixes=fixes, keywords=coverage, word_count=words)
