"""From a draft to the document a reader sees. Pure functions: nothing here touches the database, so the rules (what is
verified, what is hidden, how a date reads) are testable on their own.

The *draft* is what a student edits: an ordered list of sections, each an ordered list of references to profile items (with an
optional bullet override for self-declared items). The *document* resolves those references against the profile at one moment:
verified items are copied as they are (a bullet override on one is ignored), every entry carries whether it is verified, and
items that have since been deactivated (a revoked certificate) are dropped. A resume version stores the document, so an old
version keeps showing what it showed.
"""

from typing import Any

from app.domain.enums import DEFAULT_TITLES, SECTION_KINDS, ItemKind, SectionKey
from app.services.profile_service import ItemView

_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# A fresher's resume leads with education and projects; the order is the student's to change.
DEFAULT_ORDER = (
    SectionKey.EDUCATION, SectionKey.PROJECTS, SectionKey.EXPERIENCE, SectionKey.SKILLS, SectionKey.CERTIFICATES, SectionKey.SKILL_SCORES,
    SectionKey.ACHIEVEMENTS, SectionKey.COURSES,
)
_HIDDEN_BY_DEFAULT = {SectionKey.COURSES}  # a completed course is already implied by its certificate


def month_label(value: str | None) -> str | None:
    """``2024-06`` -> ``Jun 2024``; an ISO timestamp or date is shortened the same way; anything else is None."""
    if not value or len(value) < 7 or value[4] != "-":
        return None
    try:
        month = int(value[5:7])
    except ValueError:
        return None
    return f"{_MONTHS[month - 1]} {value[:4]}" if 1 <= month <= 12 else None


def date_range(start: str | None, end: str | None, current: bool = False) -> str | None:
    first, last = month_label(start), ("Present" if current else month_label(end))
    if first and last:
        return f"{first} – {last}"
    return first or last


def default_draft(views: list[ItemView]) -> dict[str, Any]:
    """A first draft: every section that has something in it, in a sensible order, using the profile as it stands."""
    by_kind: dict[str, list[ItemView]] = {}
    for view in views:
        by_kind.setdefault(view.item.kind, []).append(view)
    sections = []
    for key in DEFAULT_ORDER:
        items = by_kind.get(SECTION_KINDS[key].value, [])
        if items:
            sections.append(
                {"key": key.value, "title": DEFAULT_TITLES[key], "visible": key not in _HIDDEN_BY_DEFAULT, "items": [{"item_id": str(v.item.public_id), "bullets": None} for v in items]}
            )
    return {"summary": {"text": None, "visible": True}, "sections": sections, "personal": {"show_phone": True, "show_location": True, "show_links": True}}


def _entry(view: ItemView, bullets_override: list[str] | None) -> dict[str, Any]:
    kind, data, derived = ItemKind(view.item.kind), view.data, view.derived
    heading, sub, dates, location = "", None, None, None
    bullets: list[str] = list(data.get("bullets") or [])
    if kind == ItemKind.EXPERIENCE:
        heading, sub, location = data.get("title", ""), data.get("company"), data.get("location")
        dates = date_range(data.get("start_date"), data.get("end_date"), bool(data.get("current")))
    elif kind == ItemKind.EDUCATION:
        heading = ", ".join(x for x in (data.get("degree"), data.get("field_of_study")) if x)
        sub, dates = data.get("institution"), date_range(data.get("start_date"), data.get("end_date"))
        if data.get("grade"):
            bullets = [f"Grade: {data['grade']}", *bullets]
    elif kind == ItemKind.PROJECT:
        heading, sub = data.get("name", ""), ", ".join(data.get("technologies") or []) or None
        dates = date_range(data.get("start_date"), data.get("end_date"))
        if data.get("description") and not bullets:
            bullets = [data["description"]]
        if data.get("url"):
            bullets = [*bullets, data["url"]]
    elif kind == ItemKind.SKILL:
        heading = data.get("name", "")
    elif kind == ItemKind.ACHIEVEMENT:
        heading, dates = data.get("title", ""), month_label(data.get("date"))
        bullets = [data["description"]] if data.get("description") else []
    elif kind == ItemKind.CERTIFICATE:
        heading = f"{derived.get('course_title', 'Course')} — Certificate"
        dates = month_label(str(data.get("issued_at") or ""))
        bullets = [b for b in (f"Grade: {data['grade']}" if data.get("grade") else None, f"Verify: {data['verification_url']}" if data.get("verification_url") else None) if b]
    elif kind == ItemKind.COURSE:
        heading, dates = derived.get("course_title", "Course"), month_label(str(data.get("completed_at") or ""))
    elif kind == ItemKind.SKILL_SCORE:
        heading = derived.get("course_title", "Course")
        line = f"Best score {data['best_percent']:g}%"
        if derived.get("percentile") is not None:
            line += f" — {_ordinal(derived['percentile'])} percentile among {derived['cohort_size']} students"
        bullets = [line]
    if bullets_override is not None and not view.item.verified:
        bullets = bullets_override  # only ever a self-declared item's own words
    return {
        "item_id": str(view.item.public_id), "kind": kind.value, "verified": view.item.verified, "label": view.label, "heading": heading, "subheading": sub,
        "dates": dates, "location": location, "bullets": bullets,
    }


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def build_document(
    draft: dict[str, Any], *, name: str, email: str | None, phone: str | None, location: str | None, headline: str | None, links: list[dict[str, Any]],
    profile_summary: str | None, views: list[ItemView],
) -> dict[str, Any]:
    """Resolve ``draft`` against ``views`` (the student's active items). Name and email come from user-management and are marked so."""
    personal_opts = draft.get("personal") or {}
    by_id = {str(v.item.public_id): v for v in views}
    sections: list[dict[str, Any]] = []
    for section in draft.get("sections", []):
        if not section.get("visible", True):
            continue
        key = SectionKey(section["key"])
        entries = []
        for ref in section.get("items", []):
            view = by_id.get(str(ref.get("item_id")))
            if view is None or view.item.kind != SECTION_KINDS[key].value:
                continue  # deleted, deactivated or filed under the wrong section
            entries.append(_entry(view, ref.get("bullets")))
        if entries:
            sections.append({"key": key.value, "title": section.get("title") or DEFAULT_TITLES[key], "entries": entries})
    summary_cfg = draft.get("summary") or {}
    summary = (summary_cfg.get("text") or profile_summary) if summary_cfg.get("visible", True) else None
    return {
        "personal": {
            "name": name, "email": email, "name_verified": True, "headline": headline,
            "phone": phone if personal_opts.get("show_phone", True) else None, "location": location if personal_opts.get("show_location", True) else None,
            "links": links if personal_opts.get("show_links", True) else [],
        },
        "summary": summary or None,
        "sections": sections,
    }


def document_text(document: dict[str, Any]) -> str:
    """Everything a reader (or a parser) sees, as plain text: used for keyword matching, length and grammar checks."""
    parts: list[str] = [document["personal"].get("name") or "", document["personal"].get("headline") or "", document.get("summary") or ""]
    for section in document["sections"]:
        parts.append(section["title"])
        for entry in section["entries"]:
            parts.extend([entry["heading"], entry.get("subheading") or "", entry.get("dates") or "", *entry["bullets"]])
    return "\n".join(p for p in parts if p)
