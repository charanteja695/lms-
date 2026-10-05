"""A student as the job portal knows them: the facts from career-service's ``skill_profile.updated``, their stated preferences, and
what they may see. Nothing here scores; ``match_service`` does that."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.domain.enums import WorkKind
from app.matching.model import Candidate, Preferences
from app.models.match import CandidatePreference
from app.models.refs import CandidateProfile, CourseRef
from app.services import work_service


def _int(value: Any) -> int | None:
    try:
        return int(str(value)) if value not in (None, "") else None
    except ValueError:
        return None


def to_candidate(profile: CandidateProfile) -> Candidate:
    facts = profile.facts or {}
    education = tuple(" ".join(str(x) for x in (e.get("degree"), e.get("field")) if x) for e in facts.get("education") or [])
    return Candidate(
        user_id=profile.user_id, organization_id=profile.organization_id, skills=tuple(facts.get("skills") or ()), technologies=tuple(facts.get("technologies") or ()),
        job_titles=tuple(facts.get("job_titles") or ()), experience_months=int(facts.get("experience_months") or 0), graduation_year=_int(facts.get("graduation_year")),
        certificate_course_ids=frozenset(c for c in (_int(x) for x in facts.get("certificates") or []) if c is not None),
        scores={c: float(s["best_percent"]) for s in facts.get("scores") or [] if (c := _int(s.get("course_id"))) is not None and s.get("best_percent") is not None},
        education=tuple(e for e in education if e), location=facts.get("location"), target_roles=tuple(facts.get("target_roles") or ()), headline=facts.get("headline"),
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

    async def profile(self, user_id: int) -> CandidateProfile | None:
        return await self.db.get(CandidateProfile, user_id)

    async def candidate(self, user_id: int) -> Candidate | None:
        profile = await self.profile(user_id)
        return to_candidate(profile) if profile else None

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
