"""Inbound event handlers (payload contracts of the producers).

  user.created/updated/suspended/activated/deleted    user-management: {user_id, first_name, last_name, role, status, organization_id}
  institution.* / employer.*                          user-management: {organization_id, name, organization_type, status}
  application.stage_changed                           job-portal-service: {application_id, job_id, employer_id, user_id, organization_id, from, to, actor,
                                                      interview_plan_id} — to "ai_interview_invited" invites the candidate to the job's interview plan;
                                                      an application that ends (rejected, withdrawn, offer declined, placed) cancels an interview nobody started
  integrity.decided                                   proctoring-service, *for an interview* (contract: the payload carries ``interview_id`` and
                                                      ``decision`` clear | reviewed_ok | invalidated). Today proctoring-service emits it for assessment attempts
                                                      only, so nothing arrives until it is extended to interviews.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.enums import WorkKind
from app.models.interview import Interview
from app.models.refs import OrgRef, UserRef
from app.services import work_service
from app.services.interview_service import InterviewService

_ENDED = {"rejected", "withdrawn", "offer_declined", "placed"}


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
    ref.role, ref.organization_id = str(payload.get("role") or "")[:20], _int(payload.get("organization_id"))
    ref.active = payload.get("status", "active") == "active"


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
    ref.active = payload.get("status", "active") == "active"


async def handle_org_deleted(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    org_id = _int(payload.get("organization_id"))
    ref = await db.get(OrgRef, org_id) if org_id is not None else None
    if ref is not None:
        ref.active = False


async def handle_stage_changed(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    to, application_id = payload.get("to"), _int(payload.get("application_id"))
    if application_id is None:
        return
    if to == "ai_interview_invited" and payload.get("interview_plan_id"):
        await work_service.enqueue(db, WorkKind.CREATE_SCREENING, application_id, {k: payload.get(k) for k in ("application_id", "job_id", "employer_id", "user_id", "organization_id")} | {"plan_id": payload["interview_plan_id"]})
    elif to in _ENDED:
        await InterviewService(db, settings).cancel_for_application(application_id, f"application {to}")


async def handle_integrity_decided(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    interview_id = _int(payload.get("interview_id"))
    if interview_id is None:
        return
    interview = (await db.execute(select(Interview).where(Interview.public_id == interview_id))).scalar_one_or_none()
    if interview is not None and payload.get("decision") in {"clear", "reviewed_ok", "invalidated"}:
        interview.integrity_status = str(payload["decision"])
