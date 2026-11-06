"""A student as the job portal knows them: the facts from career-service's ``skill_profile.updated``, their stated preferences, and
what they may see. Nothing here scores; ``match_service`` does that."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.domain.enums import WorkKind
from app.matching.model import Candidate, Preferences
from app.models.match import CandidatePreference
from app.models.refs import CandidateProfile, CourseRef, UserRef
from app.services import work_service


def _int(value: Any) -> int | None:
    try:
        return int(str(value)) if value not in (None, "") else None
    except ValueError:
        return None


def to_candidate(
    profile: CandidateProfile | None,
    user_id: int | None = None,
    organization_id: int | None = None,
) -> Candidate:
    if profile is None:
        return Candidate(user_id=user_id or 0, organization_id=organization_id or 0)
    facts = profile.facts or {}
    edu_list = facts.get("education") or []
    education = tuple(" ".join(str(x) for x in (e.get("degree"), e.get("field") or e.get("field_of_study")) if x) for e in edu_list)
    degrees = tuple(str(e.get("degree")).strip() for e in edu_list if e.get("degree"))

    cgpa = None
    if facts.get("cgpa") not in (None, ""):
        try:
            cgpa = float(facts["cgpa"])
        except (ValueError, TypeError):
            cgpa = None
    if cgpa is None:
        for e in edu_list:
            grade = e.get("grade") or e.get("cgpa")
            if grade not in (None, ""):
                try:
                    cgpa = float(str(grade).split("/")[0].strip())
                    break
                except (ValueError, TypeError):
                    pass

    branch = str(facts["branch"]).strip() if facts.get("branch") else None
    if not branch:
        for e in edu_list:
            f = e.get("field") or e.get("field_of_study")
            if f:
                branch = str(f).strip()
                break

    grad_year = _int(facts.get("graduation_year"))
    if grad_year is None:
        for e in edu_list:
            end = str(e.get("end_date") or e.get("end_year") or "")
            if len(end) >= 4 and end[:4].isdigit():
                grad_year = int(end[:4])
                break

    backlogs = _int(facts.get("backlogs"))

    return Candidate(
        user_id=profile.user_id,
        organization_id=profile.organization_id or organization_id or 0,
        skills=tuple(facts.get("skills") or ()),
        technologies=tuple(facts.get("technologies") or ()),
        job_titles=tuple(facts.get("job_titles") or ()),
        experience_months=int(facts.get("experience_months") or 0),
        graduation_year=grad_year,
        certificate_course_ids=frozenset(c for c in (_int(x) for x in facts.get("certificates") or []) if c is not None),
        scores={c: float(s["best_percent"]) for s in facts.get("scores") or [] if (c := _int(s.get("course_id"))) is not None and s.get("best_percent") is not None},
        education=tuple(e for e in education if e),
        location=facts.get("location"),
        target_roles=tuple(facts.get("target_roles") or ()),
        headline=facts.get("headline"),
        cgpa=cgpa,
        branch=branch,
        degrees=degrees,
        backlogs=backlogs,
    )


def to_preferences(row: CandidatePreference | None) -> Preferences:
    if row is None:
        return Preferences()
    return Preferences(
        locations=tuple(row.locations or ()), open_to_remote=row.open_to_remote, roles=tuple(row.roles or ()), min_ctc=row.min_ctc,
        employment_types=tuple(row.employment_types or ()), open_to_work=row.open_to_work,
    )


class CandidateService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def profile(self, user_id: int, organization_id: int | None = None) -> CandidateProfile | None:
        row = await self.db.get(CandidateProfile, user_id)
        if row is None:
            ref = await self.db.get(UserRef, user_id)
            org_id = organization_id or (ref.organization_id if ref else None)
            row = CandidateProfile(user_id=user_id, organization_id=org_id, revision=0, facts={})
            self.db.add(row)
            try:
                await self.db.flush()
            except Exception:
                await self.db.rollback()
                row = await self.db.get(CandidateProfile, user_id)
        return row

    async def candidate(self, user_id: int, organization_id: int | None = None) -> Candidate:
        profile = await self.profile(user_id, organization_id)
        return to_candidate(profile, user_id=user_id, organization_id=organization_id)

    async def preferences(self, user_id: int) -> CandidatePreference | None:
        return await self.db.get(CandidatePreference, user_id)

    async def course_titles(self, course_ids: set[int] | None = None) -> dict[int, str]:
        stmt = select(CourseRef.course_id, CourseRef.title)
        if course_ids is not None:
            if not course_ids:
                return {}
            stmt = stmt.where(CourseRef.course_id.in_(course_ids))
        return {course_id: title for course_id, title in (await self.db.execute(stmt)).all()}

    async def save_preferences(self, user_id: int, fields: dict[str, Any]) -> CandidatePreference:
        row = await self.preferences(user_id)
        if row is None:
            row = CandidatePreference(user_id=user_id, locations=[], roles=[], employment_types=[], open_to_remote=True, open_to_work=True)
            self.db.add(row)
        for name, value in fields.items():
            setattr(row, name, value)
        row.updated_at = utcnow()
        # preferences are part of every match: re-score this student against the open jobs
        await work_service.enqueue(self.db, WorkKind.MATCH_CANDIDATE, user_id)
        await self.db.commit()
        return row
