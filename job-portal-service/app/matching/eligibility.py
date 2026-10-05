"""Eligibility: the hard rules a job sets, applied before any scoring (docs/PRODUCT.md §5.7: "Eligibility filters apply first").

A student who fails a rule is not scored for that job and cannot apply to it; the reasons say exactly what is missing, so the
student knows what to work towards. Rules: graduation year, required certificates, minimum assessment scores, and (for a restricted
job or a placement drive) the student's institution.
"""

from app.matching.model import Candidate, Eligibility, JobSpec


def check(job: JobSpec, candidate: Candidate, *, course_titles: dict[int, str]) -> Eligibility:
    reasons: list[str] = []
    rules = job.eligibility or {}

    years = rules.get("graduation_years")
    if years:
        low, high = years.get("min"), years.get("max")
        year = candidate.graduation_year
        if year is None:
            reasons.append("Add your education with an end date to your profile: this job is limited by graduation year.")
        elif (low is not None and year < low) or (high is not None and year > high):
            span = str(low) if low is not None and low == high else f"{low}–{high}" if low is not None and high is not None else f"{low} or later" if low is not None else f"{high} or earlier"
            reasons.append(f"Open to graduation years {span} (yours: {year}).")

    for raw in rules.get("certificate_course_ids") or []:
        course_id = int(raw)
        if course_id not in candidate.certificate_course_ids:
            reasons.append(f"Requires the certificate for {course_titles.get(course_id) or 'a course'}.")

    for rule in rules.get("min_scores") or []:
        course_id, minimum = int(rule["course_id"]), float(rule["min_percent"])
        title = course_titles.get(course_id) or "a course"
        have = candidate.scores.get(course_id)
        if have is None:
            reasons.append(f"Requires at least {minimum:g}% in {title} (you have no passed result yet).")
        elif have < minimum:
            reasons.append(f"Requires at least {minimum:g}% in {title} (yours: {have:g}%).")

    if job.restricted and (candidate.organization_id is None or candidate.organization_id not in job.institution_ids):
        reasons.append("This job is open only to students of selected institutions.")
    return Eligibility(eligible=not reasons, reasons=reasons)
