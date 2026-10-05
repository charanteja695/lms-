"""JSON Resume (https://jsonresume.org/schema) export: the portable format other resume tools and job boards read.

Built from the resolved document, so it shows exactly what the PDF shows. Dates are ``YYYY-MM`` where the student gave one;
the schema's ``x-lms`` block (allowed as an extension) says which entries are platform-verified.
"""

from typing import Any


def to_json_resume(document: dict[str, Any], *, raw_items: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """``raw_items`` maps an item id to its stored data (ISO dates are read from it, not from the display strings)."""
    personal = document["personal"]
    basics: dict[str, Any] = {"name": personal["name"], "label": personal.get("headline") or "", "summary": document.get("summary") or ""}
    if personal.get("email"):
        basics["email"] = personal["email"]
    if personal.get("phone"):
        basics["phone"] = personal["phone"]
    if personal.get("location"):
        basics["location"] = {"address": personal["location"]}
    if personal.get("links"):
        basics["profiles"] = [{"network": link.get("label") or "Link", "url": link["url"]} for link in personal["links"]]
    resume: dict[str, Any] = {"basics": basics, "work": [], "education": [], "projects": [], "skills": [], "certificates": [], "awards": [], "x-lms": {"verified_items": []}}
    for section in document["sections"]:
        for entry in section["entries"]:
            data = raw_items.get(entry["item_id"], {})
            if entry["verified"]:
                resume["x-lms"]["verified_items"].append({"kind": entry["kind"], "heading": entry["heading"]})
            kind = entry["kind"]
            bullets = [b for b in entry["bullets"] if not b.startswith(("Verify:", "Grade:"))] if kind in {"certificate", "education"} else entry["bullets"]
            if kind == "experience":
                job = {"name": data.get("company", ""), "position": data.get("title", ""), "startDate": data.get("start_date", ""), "highlights": bullets}
                if data.get("end_date"):
                    job["endDate"] = data["end_date"]
                if data.get("location"):
                    job["location"] = data["location"]
                resume["work"].append(job)
            elif kind == "education":
                edu = {"institution": data.get("institution", ""), "studyType": data.get("degree", ""), "area": data.get("field_of_study", ""), "startDate": data.get("start_date", "")}
                if data.get("end_date"):
                    edu["endDate"] = data["end_date"]
                if data.get("grade"):
                    edu["score"] = data["grade"]
                resume["education"].append(edu)
            elif kind == "project":
                project = {"name": data.get("name", ""), "description": data.get("description", ""), "highlights": bullets, "keywords": data.get("technologies", [])}
                if data.get("url"):
                    project["url"] = data["url"]
                resume["projects"].append(project)
            elif kind == "skill":
                resume["skills"].append({"name": data.get("name", ""), "keywords": []})
            elif kind == "certificate":
                cert = {"name": entry["heading"], "issuer": "LMS", "date": str(data.get("issued_at") or "")[:10]}
                if data.get("verification_url"):
                    cert["url"] = data["verification_url"]
                resume["certificates"].append(cert)
            elif kind == "achievement":
                resume["awards"].append({"title": entry["heading"], "date": data.get("date", ""), "summary": " ".join(entry["bullets"])})
    return {k: v for k, v in resume.items() if v not in ([], {})} | {"x-lms": resume["x-lms"]}
