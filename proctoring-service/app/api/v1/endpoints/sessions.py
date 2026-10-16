from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import (
    CaseIdParam,
    CurrentAuth,
    DbSession,
    EventsRateLimit,
    RedisDep,
    RequestCtx,
    RequireStudent,
    SessionIdParam,
    SettingsDep,
    SnapshotRateLimit,
)
from app.api.responses import AUTHENTICATED, errors
from app.core.config import Settings
from app.core.time import utcnow
from app.domain.enums import LIVENESS_POSES
from app.models.case import IntegrityCase
from app.models.session import ProctorSession
from app.schemas.proctoring import (
    AppealIn,
    DirectiveOut,
    EventsIn,
    EventsResponse,
    HeartbeatIn,
    HeartbeatResponse,
    PrecheckIn,
    PrecheckResponse,
    Requirements,
    SessionCreate,
    SessionOut,
    SessionResponse,
    SnapshotOut,
    SnapshotRegisterIn,
    SnapshotResponse,
    SnapshotUploadIn,
    StudentCaseOut,
    StudentCaseResponse,
    StudentCasesResponse,
    UploadOut,
    UploadResponse,
)
from app.services.case_service import CaseService
from app.services.session_service import SessionService, needs_for
from app.services.snapshot_service import SnapshotService

router = APIRouter(tags=["Proctoring sessions"])


def _requirements(session: ProctorSession, settings: Settings) -> Requirements:
    return Requirements(
        level=session.level, consent_version=settings.CONSENT_VERSION, needs=needs_for(session.level, session.screen_share, settings.LIVENESS_REQUIRED),
        snapshot_interval_seconds=settings.SNAPSHOT_INTERVAL_SECONDS, heartbeat_interval_seconds=settings.HEARTBEAT_INTERVAL_SECONDS,
        min_bandwidth_kbps=settings.MIN_BANDWIDTH_KBPS_STRICT if session.level == "strict" else 0,
        screen_share=session.level == "strict" and session.screen_share,
        audio_interval_seconds=settings.AUDIO_INTERVAL_SECONDS if session.level == "strict" else 0,
        audio_clip_seconds=settings.AUDIO_CLIP_SECONDS if session.level == "strict" else 0,
        liveness_poses=list(LIVENESS_POSES) if session.level == "strict" and settings.LIVENESS_REQUIRED else [],
        video_recording=session.level == "strict" and settings.VIDEO_RECORDING_ENABLED,
        video_chunk_seconds=settings.VIDEO_CHUNK_SECONDS if session.level == "strict" and settings.VIDEO_RECORDING_ENABLED else 0,
    )


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=201,
    summary="Start the pre-check for a proctored test",
    description="Creates (or returns the open) pre-check session for this student and test. `requirements` says what the "
    "browser must do next: accept the consent, run the system check and, for strict tests, capture an ID photo and a face "
    "photo. 404 `TEST_NOT_PROCTORED` if the test has no proctoring.",
    responses=errors(*AUTHENTICATED, 404),
)
async def create_session(data: SessionCreate, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep, ctx: RequestCtx) -> SessionResponse:
    session = await SessionService(db, settings, redis).create(auth, data.test_id, ctx)
    return SessionResponse(message="Pre-check started.", session=SessionOut.model_validate(session), requirements=_requirements(session, settings))


@router.get("/sessions/{session_id}", response_model=SessionResponse, summary="My session", responses=errors(*AUTHENTICATED, 404))
async def get_session(session_id: SessionIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep) -> SessionResponse:
    session = await SessionService(db, settings, redis).get_owned(session_id, auth.user_id)
    return SessionResponse(message="Session retrieved successfully.", session=SessionOut.model_validate(session), requirements=_requirements(session, settings))


@router.post(
    "/sessions/{session_id}/precheck",
    response_model=PrecheckResponse,
    summary="Submit the system check and consent",
    description="Returns `ready: true` when everything required is in place, and then assessment-service will let the student "
    "start. Otherwise `failures` lists what to fix; the check can simply be retried.",
    responses=errors(*AUTHENTICATED, 404, 409, 422),
)
async def precheck(session_id: SessionIdParam, data: PrecheckIn, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep, ctx: RequestCtx) -> PrecheckResponse:
    service = SessionService(db, settings, redis)
    session = await service.get_owned(session_id, auth.user_id, lock=True)
    failures = await service.precheck(session, data, ctx)
    return PrecheckResponse(message="You are ready." if not failures else "Some checks did not pass.", ready=not failures, failures=failures, session=SessionOut.model_validate(session))


@router.post(
    "/sessions/{session_id}/snapshots/upload-url",
    response_model=UploadResponse,
    dependencies=[SnapshotRateLimit],
    summary="A presigned upload for an ID photo, face photo, liveness frame, periodic snapshot, screen capture, audio clip or video chunk",
    description="Upload the file straight to `upload.url` with `upload.fields` (a multipart POST), then register it. Strict "
    "proctoring only. Identity photos before the test; periodic snapshots (about every `snapshot_interval_seconds`), "
    "screen captures and audio only while it runs.",
    responses=errors(*AUTHENTICATED, 404, 409, 422, 429),
)
async def snapshot_upload_url(session_id: SessionIdParam, data: SnapshotUploadIn, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep) -> UploadResponse:
    session = await SessionService(db, settings, redis).get_owned(session_id, auth.user_id)
    upload = await SnapshotService(db, settings).upload_url(session, data.kind, data.content_type, pose=data.pose)
    return UploadResponse(message="Upload URL issued.", file=UploadOut(**upload))


@router.post(
    "/sessions/{session_id}/snapshots",
    response_model=SnapshotResponse,
    status_code=201,
    dependencies=[SnapshotRateLimit],
    summary="Register an uploaded snapshot",
    description="The file must really be in storage and belong to this session. It is queued for AI analysis (or stored "
    "and marked skipped when no analyzer is configured or under heavy load) and deleted after the retention period.",
    responses=errors(*AUTHENTICATED, 404, 409, 422, 429),
)
async def register_snapshot(session_id: SessionIdParam, data: SnapshotRegisterIn, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep) -> SnapshotResponse:
    session = await SessionService(db, settings, redis).get_owned(session_id, auth.user_id, lock=True)
    snapshot = await SnapshotService(db, settings).register(session, data.kind, data.key, data.taken_at)
    return SnapshotResponse(message="Snapshot registered.", snapshot=SnapshotOut.model_validate(snapshot))


@router.post(
    "/sessions/{session_id}/heartbeat",
    response_model=HeartbeatResponse,
    summary="Proof of life, and instructions from staff",
    description="Send about every `heartbeat_interval_seconds`. The response carries any warnings, pauses or terminations "
    "staff issued since the last one. A client that goes quiet for `HEARTBEAT_LOST_AFTER_SECONDS` is scored.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def heartbeat(session_id: SessionIdParam, data: HeartbeatIn, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep, ctx: RequestCtx) -> HeartbeatResponse:
    service = SessionService(db, settings, redis)
    session = await service.get_owned(session_id, auth.user_id, lock=True)
    directives = await service.heartbeat(session, ctx, data.device_fingerprint)
    return HeartbeatResponse(
        message="OK", session_status=session.status, risk_score=session.risk_score, directives=[DirectiveOut.model_validate(d) for d in directives],
        snapshot_interval_seconds=settings.SNAPSHOT_INTERVAL_SECONDS, server_time=utcnow(),
    )


@router.post(
    "/sessions/{session_id}/events",
    response_model=EventsResponse,
    dependencies=[EventsRateLimit],
    summary="Report browser events (batched)",
    description="Types: `fullscreen_exit`, `tab_switch`, `window_blur`, `copy_paste`, `right_click`, `devtools_open`, "
    "`multiple_monitors`, `network_lost`, and (strict) `camera_off`, `mic_off`, `screen_share_stopped`. Each adds weighted "
    "risk, capped per type. Types a client may not report (AI findings, staff actions) are rejected in the response.",
    responses=errors(*AUTHENTICATED, 404, 409, 422, 429),
)
async def report_events(session_id: SessionIdParam, data: EventsIn, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep) -> EventsResponse:
    service = SessionService(db, settings, redis)
    session = await service.get_owned(session_id, auth.user_id, lock=True)
    accepted, rejected = await service.record_client_events(session, data.events)
    return EventsResponse(message="Events recorded.", accepted=accepted, rejected=rejected, risk_score=session.risk_score)


def _student_case(case: IntegrityCase, service: CaseService) -> StudentCaseOut:
    out = StudentCaseOut.model_validate(case)
    out.can_appeal = service.can_appeal(case)
    return out


@router.get(
    "/my/cases",
    response_model=StudentCasesResponse,
    summary="Integrity outcomes of my attempts",
    description="What happened to my proctored attempts, and whether I can appeal (an invalidation, once).",
    responses=errors(*AUTHENTICATED),
)
async def my_cases(auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> StudentCasesResponse:
    service = CaseService(db, settings)
    rows = (await db.execute(select(IntegrityCase).where(IntegrityCase.user_id == auth.user_id).order_by(IntegrityCase.created_at.desc()).limit(100))).scalars()
    return StudentCasesResponse(message="Cases retrieved successfully.", cases=[_student_case(c, service) for c in rows])


@router.post(
    "/cases/{case_id}/appeal",
    response_model=StudentCaseResponse,
    summary="Appeal an invalidation (once)",
    description="Only the student, only an invalidation, once, within the appeal window. A different exam manager decides it.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def appeal_case(case_id: CaseIdParam, data: AppealIn, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> StudentCaseResponse:
    service = CaseService(db, settings)
    case = await service.appeal(await service.get(case_id), auth, data.reason)
    return StudentCaseResponse(message="Your appeal has been recorded.", case=_student_case(case, service))
