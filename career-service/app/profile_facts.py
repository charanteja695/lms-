"""The facts about a student that other services may match on (job-portal-service's matching and shortlisting), carried by
``skill_profile.updated``. Pure functions over the stored items.

Only what a hiring decision may legitimately look at goes here: skills, technologies, role titles, months of experience,
education level and graduation year, verified certificates and scores. Never the name, email, photo, date of birth, gender or
institution: protected attributes are not in the event, so no consumer can score on them by accident.
"""

from collections.abc import Iterable
from datetime import date
from typing import Any

from app.models.profile import Profile, ProfileItem


def _months(start: str | None, end: str | None, current: bool, today: date) -> int:
    if not start or len(start) < 7:
        return 0
    try:
        sy, sm = int(start[:4]), int(start[5:7])
        ey, em = (today.year, today.month) if current or not end else (int(end[:4]), int(end[5:7]))
    except ValueError:
        return 0
    return max((ey - sy) * 12 + (em - sm) + 1, 0)


def matching_facts(profile: Profile, items: Iterable[ProfileItem], *, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    skills: list[str] = []
    technologies: list[str] = []
    titles: list[str] = []
    education: list[dict[str, Any]] = []
    certificates: list[str] = []
    scores: list[dict[str, Any]] = []
    months = 0
    projects = 0
    for item in items:
        if not item.active:
            continue
        data = item.data
        if item.kind == "skill":
            skills.append(str(data.get("name", "")))
        elif item.kind == "project":
            projects += 1
            technologies.extend(str(t) for t in data.get("technologies") or [])
        elif item.kind == "experience":
            titles.append(str(data.get("title", "")))
            months += _months(data.get("start_date"), data.get("end_date"), bool(data.get("current")), today)
        elif item.kind == "education":
            end = str(data.get("end_date") or "")
            education.append({"degree": data.get("degree"), "field": data.get("field_of_study"), "end_year": int(end[:4]) if end[:4].isdigit() else None})
        elif item.kind == "certificate":
            certificates.append(str(data.get("course_id")))
        elif item.kind == "skill_score":
            scores.append({"course_id": str(data.get("course_id")), "best_percent": data.get("best_percent")})
    years = [e["end_year"] for e in education if e["end_year"]]
    return {
        "skills": sorted({s for s in skills if s}, key=str.lower),
        "technologies": sorted({t for t in technologies if t}, key=str.lower),
        "job_titles": [t for t in titles if t],
        "experience_months": months,
        "projects": projects,
        "education": education,
        "graduation_year": max(years) if years else None,
        "certificates": sorted(set(certificates)),
        "scores": scores,
        "location": profile.location,
        "target_roles": list(profile.target_roles or []),
        "headline": profile.headline,
    }
