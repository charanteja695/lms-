"""The match score, 0–100 (docs/PRODUCT.md §5.7): a weighted blend of

  skill overlap, weighted by verified scores   50   a required skill counts 1, a preferred one 0.5; a skill the candidate merely
                                                    declares earns 0.7 of its weight, a skill backed by a certificate or an
                                                    assessment result earns 0.85–1.0 (more the higher the verified score)
  semantic similarity of profile and job        20   embeddings when available, word overlap otherwise (the method is recorded)
  relevant certificates held                    10   certificates whose course is about the job's skills or title, two earn it all
  preferences (location, role, salary, type)    20   35 / 30 / 20 / 15 of the points; a preference left unset earns half its points

The weights are settings and must add up to 100. Every score comes with an explanation a student can read ("Matches 6/8 required
skills; missing: Docker, AWS"). Nothing personal is an input: see ``Candidate``.
"""

from dataclasses import dataclass

from app.matching.model import Candidate, JobSpec, MatchResult, Preferences
from app.matching.text import canonical, tokens

SELF_DECLARED_CREDIT = 0.7
VERIFIED_BASE_CREDIT = 0.85
VERIFIED_SCORE_BONUS = 0.15
PREFERENCE_SHARES = {"location": 0.35, "role": 0.30, "salary": 0.20, "type": 0.15}


@dataclass(frozen=True, slots=True)
class Weights:
    skills: int = 50
    semantic: int = 20
    certificates: int = 10
    preferences: int = 20


def verified_terms(courses: dict[int, str], certificate_course_ids: frozenset[int], scores: dict[int, float]) -> dict[str, float]:
    """Skill terms a candidate has *verified*, with the credit each earns: the words of the titles of the courses they hold a certificate
    for or have a passed assessment in. ``{"python": 0.98, "sql": 0.85}``. Higher verified scores earn more."""
    credit: dict[str, float] = {}
    for course_id in certificate_course_ids | set(scores):
        title = courses.get(course_id)
        if not title:
            continue
        best = scores.get(course_id)
        value = VERIFIED_BASE_CREDIT + (VERIFIED_SCORE_BONUS * min(max(best, 0.0), 100.0) / 100 if best is not None else 0.0)
        for term in set(tokens(title)):
            credit[term] = max(credit.get(term, 0.0), value)
    return credit


def _skill_credit(skill: str, declared: set[str], verified: dict[str, float]) -> tuple[float, bool]:
    """(credit 0..1, backed by a verified result)."""
    term = canonical(skill)
    parts = set(tokens(skill)) or {term}
    backed = max((verified.get(p, 0.0) for p in parts | {term}), default=0.0)
    if term in declared or parts <= declared:
        return max(SELF_DECLARED_CREDIT, backed), backed > 0
    if backed:  # verified by a course the candidate finished, though never listed as a skill
        return backed, True
    return 0.0, False


def _skills_part(job: JobSpec, candidate: Candidate, verified: dict[str, float]) -> tuple[float, list[str]]:
    declared = {canonical(s) for s in (*candidate.skills, *candidate.technologies)}
    explanation: list[str] = []
    total = gained = 0.0
    matched_required: list[str] = []
    missing_required: list[str] = []
    matched_preferred = 0
    verified_hits: list[str] = []
    for skill in job.required_skills:
        credit, backed = _skill_credit(skill, declared, verified)
        total += 1.0
        gained += credit
        (matched_required if credit else missing_required).append(skill)
        if backed:
            verified_hits.append(skill)
    for skill in job.preferred_skills:
        credit, backed = _skill_credit(skill, declared, verified)
        total += 0.5
        gained += 0.5 * credit
        matched_preferred += 1 if credit else 0
        if backed:
            verified_hits.append(skill)
    n = len(job.required_skills)
    line = f"Matches {len(matched_required)}/{n} required skills"
    if missing_required:
        line += f"; missing: {', '.join(missing_required)}"
    explanation.append(line)
    if job.preferred_skills:
        explanation.append(f"Preferred skills: {matched_preferred}/{len(job.preferred_skills)}")
    if verified_hits:
        explanation.append(f"Verified on the platform: {', '.join(verified_hits)}")
    return (gained / total if total else 0.5), explanation


def _certificates_part(job: JobSpec, candidate: Candidate, courses: dict[int, str]) -> tuple[float, list[str]]:
    wanted = {canonical(s) for s in (*job.required_skills, *job.preferred_skills)} | set(tokens(job.title))
    relevant = [courses[c] for c in candidate.certificate_course_ids if c in courses and set(tokens(courses[c])) & wanted]
    if not relevant:
        return 0.0, []
    return min(1.0, len(relevant) / 2), [f"Relevant certificate{'s' if len(relevant) > 1 else ''}: {', '.join(sorted(relevant))}"]


def _pref_location(job: JobSpec, candidate: Candidate, prefs: Preferences) -> tuple[float, str | None]:
    if job.location_type in {"remote", "hybrid"} and prefs.open_to_remote:
        return 1.0, "Remote-friendly" if job.location_type == "remote" else "Hybrid"
    wanted = {loc.lower().split(",")[0].strip() for loc in prefs.locations}
    if not wanted and candidate.location:
        wanted = {candidate.location.lower().split(",")[0].strip()}
    if not wanted:
        return 0.5, None
    offered = {loc.lower().split(",")[0].strip() for loc in job.locations}
    if wanted & offered:
        return 1.0, f"Location matches ({', '.join(sorted(wanted & offered)).title()})"
    return 0.0, "Location differs from your preference"


def _pref_role(job: JobSpec, candidate: Candidate, prefs: Preferences) -> tuple[float, str | None]:
    roles = [*prefs.roles, *candidate.target_roles]
    if not roles:
        return 0.5, None
    title = set(tokens(job.title))
    best = 0.0
    for role in roles:
        words = set(tokens(role))
        if words and title:
            best = max(best, len(words & title) / len(words | title))
    if best >= 0.34:
        return 1.0, "Matches a role you are looking for"
    return (0.5, None) if best > 0 else (0.0, None)


def _pref_salary(job: JobSpec, prefs: Preferences) -> tuple[float, str | None]:
    if prefs.min_ctc is None or job.ctc_max is None:
        return 0.5, None
    return (1.0, "Pay meets your minimum") if job.ctc_max >= prefs.min_ctc else (0.0, "Pay is below your minimum")


def _pref_type(job: JobSpec, prefs: Preferences) -> tuple[float, str | None]:
    if not prefs.employment_types:
        return 0.5, None
    return (1.0, None) if job.employment_type in prefs.employment_types else (0.0, "Not a kind of job you asked for")


def _preferences_part(job: JobSpec, candidate: Candidate, prefs: Preferences) -> tuple[float, list[str]]:
    parts = {"location": _pref_location(job, candidate, prefs), "role": _pref_role(job, candidate, prefs), "salary": _pref_salary(job, prefs), "type": _pref_type(job, prefs)}
    value = sum(PREFERENCE_SHARES[name] * credit for name, (credit, _) in parts.items())
    return value, [note for _, note in parts.values() if note]


def _duration(months: int) -> str:
    if months >= 12:
        years = months / 12
        return f"{years:g} year{'s' if years != 1 else ''}"
    return f"{months} month{'s' if months != 1 else ''}"


def score(
    job: JobSpec, candidate: Candidate, prefs: Preferences, *, courses: dict[int, str], semantic: float, semantic_method: str, weights: Weights = Weights()  # noqa: B008
) -> MatchResult:
    """Score an *eligible* candidate against a job. ``semantic`` is the similarity already scaled to 0..1 (see ``app.matching.text``)."""
    verified = verified_terms(courses, candidate.certificate_course_ids, candidate.scores)
    skills, skill_notes = _skills_part(job, candidate, verified)
    certs, cert_notes = _certificates_part(job, candidate, courses)
    pref, pref_notes = _preferences_part(job, candidate, prefs)
    breakdown = {
        "skills": round(weights.skills * skills, 1), "semantic": round(weights.semantic * semantic, 1),
        "certificates": round(weights.certificates * certs, 1), "preferences": round(weights.preferences * pref, 1),
    }
    total = round(sum(breakdown.values()))
    notes = [*skill_notes, *cert_notes, *pref_notes, f"Profile and job description similarity: {round(semantic * 100)}% ({'embeddings' if semantic_method == 'dense' else 'word overlap'})"]
    if job.experience_min_months and candidate.experience_months < job.experience_min_months:
        notes.append(f"Asks for {_duration(job.experience_min_months)} of experience; you have {_duration(candidate.experience_months)}")
    return MatchResult(score=max(0, min(100, total)), breakdown=breakdown, explanation=notes, semantic_method=semantic_method, semantic_similarity=round(semantic, 3))


def required_coverage(job: JobSpec, candidate: Candidate, courses: dict[int, str]) -> tuple[int, int]:
    """(required skills the candidate has, required skills the job lists): declared or backed by a finished course."""
    verified = verified_terms(courses, candidate.certificate_course_ids, candidate.scores)
    declared = {canonical(s) for s in (*candidate.skills, *candidate.technologies)}
    matched = sum(1 for skill in job.required_skills if _skill_credit(skill, declared, verified)[0] > 0)
    return matched, len(job.required_skills)
