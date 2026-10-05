"""What this service consumes from ``lms:events`` (payload contracts of the producers):

  course.published       catalog-service: the whole tree, with titles and note text (added for this service)   -> content index
  course.retired         catalog-service: {"course_id", "version_id", ...}                                     -> retire that version's chunks
  transcript.ready       media-service (contract only, not emitted yet): {"media_asset_id", "segments": [{"start", "end", "text"}]}
  enrollment.created     learning-service: {"enrollment_id", "student_user_id", "organization_id", "version_id", ...}
  enrollment.removed     learning-service: {"enrollment_id", "student_user_id", "version_id", ...}
  attempt.started        assessment-service: {"attempt_id", "user_id", "test_kind", "course_id", "deadline_at", ...}
  attempt.submitted      assessment-service: same shape          -> the student may use the tutor again
  attempt.finalized      assessment-service: adds "result", "percent"
  certificate.issued     certificate-service: {"certificate_id", "student_user_id", "course_id", "grade", "issued_at", ...}
  certificate.revoked    certificate-service: {"certificate_id", ...}

Everything but the content events is a small upsert into a read-model; the router records each event id so one is applied
at most once.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.enums import AttemptState
from app.models.refs import AttemptRef, CertificateRef, EnrollmentRef
from app.services.index_service import IndexService

_RANK = {AttemptState.IN_PROGRESS: 0, AttemptState.SUBMITTED: 1, AttemptState.FINALIZED: 2}


def _when(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


async def handle_course_published(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await IndexService(db, settings).on_course_published(payload)


async def handle_course_retired(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await IndexService(db, settings).on_course_retired(payload)


async def handle_transcript_ready(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await IndexService(db, settings).on_transcript_ready(payload)


async def handle_enrollment(db: AsyncSession, settings: Settings, payload: dict[str, Any], *, active: bool) -> None:
    enrollment_id = int(payload["enrollment_id"])
    ref = await db.get(EnrollmentRef, enrollment_id)
    if ref is None:
        ref = EnrollmentRef(enrollment_id=enrollment_id, student_user_id=int(payload["student_user_id"]), version_id=int(payload["version_id"]))
        db.add(ref)
    ref.student_user_id, ref.version_id, ref.active = int(payload["student_user_id"]), int(payload["version_id"]), active
    if payload.get("organization_id"):
        ref.organization_id = int(payload["organization_id"])


async def handle_enrollment_created(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await handle_enrollment(db, settings, payload, active=True)


async def handle_enrollment_removed(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await handle_enrollment(db, settings, payload, active=False)


async def _attempt(db: AsyncSession, payload: dict[str, Any], state: AttemptState) -> AttemptRef:
    attempt_id = int(payload["attempt_id"])
    ref = await db.get(AttemptRef, attempt_id)
    if ref is None:
        ref = AttemptRef(attempt_id=attempt_id, state=state)
        db.add(ref)
    elif _RANK[AttemptState(ref.state)] <= _RANK[state]:  # events can arrive out of order: never move an attempt backwards
        ref.state = state
    if payload.get("user_id"):
        ref.user_id = int(payload["user_id"])
    ref.test_kind = payload.get("test_kind") or ref.test_kind or ""
    if payload.get("course_id"):
        ref.course_id = int(payload["course_id"])
    if payload.get("deadline_at"):
        ref.deadline_at = _when(payload["deadline_at"])
    return ref


async def handle_attempt_started(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await _attempt(db, payload, AttemptState.IN_PROGRESS)


async def handle_attempt_submitted(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    await _attempt(db, payload, AttemptState.SUBMITTED)


async def handle_attempt_finalized(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    ref = await _attempt(db, payload, AttemptState.FINALIZED)
    ref.result = payload.get("result")
    ref.percent = float(payload["percent"]) if payload.get("percent") is not None else None


async def handle_certificate_issued(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    certificate_id = int(payload["certificate_id"])
    ref = await db.get(CertificateRef, certificate_id)
    if ref is None:
        ref = CertificateRef(certificate_id=certificate_id, student_user_id=int(payload["student_user_id"]), course_id=int(payload["course_id"]), status="issued")
        db.add(ref)
    ref.status, ref.grade, ref.issued_at = "issued", payload.get("grade"), _when(payload.get("issued_at"))


async def handle_certificate_revoked(db: AsyncSession, settings: Settings, payload: dict[str, Any]) -> None:
    ref = await db.get(CertificateRef, int(payload["certificate_id"]))
    if ref is not None:
        ref.status = "revoked"
