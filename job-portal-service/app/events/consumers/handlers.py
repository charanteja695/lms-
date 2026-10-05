"""Inbound event handlers (payload contracts of the producers).

  user.created/updated/suspended/activated/deleted    user-management: {user_id, email, first_name, last_name, role, status, organization_id}
  institution.* / employer.*                          user-management: {organization_id, name, organization_type, industry, status}
  course.published                                    catalog-service: {course_id, title, ...}
  skill_profile.updated                               career-service: {user_id, organization_id, revision, facts: {skills, technologies, job_titles,
                                                      experience_months, education[{degree,field,end_year}], graduation_year, certificates[course ids],
                                                      scores[{course_id, best_percent}], location, target_roles, headline}}
  attempt.finalized                                   assessment-service (test_kind "hiring" only): {attempt_id, test_id, user_id, result, percent,
                                                      integrity_status, revision}
  interview.completed                                 ai-interview-service: {application_id, interview_id, recommendation, score, report}

``integrity.decided`` is not consumed here: assessment-service folds the integrity decision into ``attempt.finalized`` (a higher
``revision`` when a decision changes the result), which is what the pipeline follows. ``resume.updated`` is not needed either: the resume
a candidate applies with is frozen by career-service at the moment they apply (``POST /internal/resumes/{id}/snapshot``).
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.time import utcnow
from app.domain.enums import EmployerStatus, WorkKind
from app.models.refs import CandidateProfile, CourseRef, OrgRef, UserRef
from app.services import work_service
from app.services.application_events import ApplicationEvents
from app.services.employer_service import EmployerService


def _int(value: Any) -> int | None:
    try:
        return int(str(value)) if value not in (None, "") else None
    except ValueError:
        return None


async def handle_user_upserted(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    user_id = _int(payload.get("user_id"))
    if user_id is None:
        return
    ref = await db.get(UserRef, user_id)
    if ref is None:
        ref = UserRef(user_id=user_id)
        db.add(ref)
    ref.first_name, ref.last_name = str(payload.get("first_name") or "")[:100], str(payload.get("last_name") or "")[:100]
    ref.email = str(payload["email"])[:320] if payload.get("email") else ref.email
    ref.role = str(payload.get("role") or "")[:20]
    ref.organization_id = _int(payload.get("organization_id"))
    ref.active = payload.get("status", "active") == "active"
    profile = await db.get(CandidateProfile, user_id)
    if profile is not None and ref.organization_id is not None and profile.organization_id != ref.organization_id:
        profile.organization_id = ref.organization_id  # a student moved institution: drives and restricted jobs follow
        await work_service.enqueue(db, WorkKind.MATCH_CANDIDATE, user_id)


async def handle_user_deleted(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    user_id = _int(payload.get("user_id"))
    ref = await db.get(UserRef, user_id) if user_id is not None else None
    if ref is not None:
        ref.active = False


async def handle_org_upserted(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    org_id = _int(payload.get("organization_id"))
    if org_id is None:
        return
    ref = await db.get(OrgRef, org_id)
    if ref is None:
        ref = OrgRef(org_id=org_id)
        db.add(ref)
    ref.name = str(payload.get("name") or ref.name or "")[:200]
    ref.org_type = str(payload.get("organization_type") or ref.org_type or "")[:12]
    ref.industry = payload.get("industry") or ref.industry
    active = payload.get("status", "active") == "active"
    ref.active = active
    await _sync_employer(db, ref, active)


async def handle_org_deleted(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    org_id = _int(payload.get("organization_id"))
    ref = await db.get(OrgRef, org_id) if org_id is not None else None
    if ref is not None:
        ref.active = False
        await _sync_employer(db, ref, False)


async def _sync_employer(db: AsyncSession, ref: OrgRef, active: bool) -> None:
    """An employer whose account is suspended in user-management is suspended here too (its jobs pause), and reinstated when the account is."""
    if ref.org_type != "employer":
        return
    service = EmployerService(db)
    profile = await service.get(ref.org_id)
    if profile is None:
        return
    if not active and profile.status == EmployerStatus.VERIFIED:
        await service.suspend(ref.org_id, source="account", by_user_id=None, note="Account suspended")
    elif active and profile.status == EmployerStatus.SUSPENDED and profile.suspension_source == "account":
        await service.reinstate(ref.org_id, source="account")


async def handle_course_published(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    course_id = _int(payload.get("course_id"))
    if course_id is None:
        return
    ref = await db.get(CourseRef, course_id)
    if ref is None:
        ref = CourseRef(course_id=course_id, title="")
        db.add(ref)
    ref.title = str(payload.get("title") or ref.title)[:300]


async def handle_skill_profile_updated(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    user_id, revision = _int(payload.get("user_id")), int(payload.get("revision") or 0)
    if user_id is None or not isinstance(payload.get("facts"), dict):
        return
    profile = await db.get(CandidateProfile, user_id)
    if profile is not None and revision <= profile.revision:
        return  # an older or repeated update
    if profile is None:
        profile = CandidateProfile(user_id=user_id, revision=0, facts={})
        db.add(profile)
    profile.facts, profile.revision = payload["facts"], revision
    profile.organization_id = _int(payload.get("organization_id")) or profile.organization_id
    profile.updated_by_event_at = utcnow()
    profile.embedding, profile.embedding_revision = None, None
    await work_service.enqueue(db, WorkKind.MATCH_CANDIDATE, user_id)


async def handle_attempt_finalized(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    if payload.get("test_kind") != "hiring":
        return
    await ApplicationEvents(db, settings).assessment_result(payload)


async def handle_interview_completed(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await ApplicationEvents(db, settings).interview_completed(payload)
