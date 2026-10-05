"""Taking an interview: a student's mock practice, or a screening interview job-portal-service invited them to (docs/PRODUCT.md §5.8).

Consent, then start (the server's clock takes over from there), then turns — typed or spoken (STT/TTS run through ai-gateway; text always
works even when speech is not configured) — and, in the coding round, running code through code-execution-service. The report never shows
the recommendation to the candidate; only a company's recruiters and the platform's careers managers see that (``employer.py``)."""

from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    CodeExecDep,
    DbSession,
    GatewayDep,
    IdempotencyKeyHeader,
    InterviewIdParam,
    RequireStudent,
    SettingsDep,
    TurnRateLimit,
    WriteRateLimit,
)
from app.api.presenters import appeal_out, interview_out, report_out, turn_out
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import ValidationFailedError
from app.domain.enums import InterviewStatus, PlanKind
from app.models.interview import InterviewTurn
from app.schemas.interview import (
    AnswerText,
    AppealRequest,
    AppealResponse,
    CodeRunOut,
    CodeRunRequest,
    CodeRunResponse,
    ConsentOut,
    ConsentRequest,
    ConsentResponse,
    InterviewPage,
    InterviewResponse,
    MockInterviewCreate,
    ReportResponse,
    TimeLeftOut,
    TranscriptResponse,
    TurnPair,
    TurnResponse,
)
from app.services.conduct_service import ConductService
from app.services.evaluation_service import EvaluationService
from app.services.interview_service import InterviewService
from app.services.plan_service import PlanService
from app.services.review_service import ReviewService

router = APIRouter(prefix="/student/interviews", tags=["Interviews (student)"])
MAX_AUDIO_BYTES = 15 * 1024 * 1024


@router.post(
    "", response_model=InterviewResponse, status_code=201, summary="Start a practice interview", responses=errors(*AUTHENTICATED, 409, 429),
    description="Up to your monthly allowance; only one practice interview may be open at a time. The invitation must be started within its window.",
    dependencies=[WriteRateLimit],
)
async def create_mock_interview(body: MockInterviewCreate, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> InterviewResponse:
    plan = await PlanService(db, settings).get_for_student(body.plan_id)
    interview = await InterviewService(db, settings).create_mock(auth, plan)
    return InterviewResponse(message="Practice interview created: accept the consent, then start.", interview=interview_out(interview))


@router.get("", response_model=InterviewPage, summary="My interviews", responses=errors(*AUTHENTICATED))
async def list_my_interviews(
    auth: RequireStudent, db: DbSession, settings: SettingsDep, status: Annotated[InterviewStatus | None, Query()] = None, kind: Annotated[PlanKind | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1, per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> InterviewPage:
    interviews, total = await InterviewService(db, settings).list_mine(auth.user_id, status=status.value if status else None, kind=kind.value if kind else None, page=page, per_page=per_page)
    return InterviewPage(
        message="", interviews=[interview_out(i) for i in interviews],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


@router.get("/{interview_id}", response_model=InterviewResponse, summary="One of my interviews", responses=errors(*AUTHENTICATED))
async def get_my_interview(interview_id: InterviewIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> InterviewResponse:
    interview = await InterviewService(db, settings).get_mine(auth.user_id, interview_id)
    return InterviewResponse(message="", interview=interview_out(interview))


@router.get(
    "/{interview_id}/transcript", response_model=TranscriptResponse, summary="The conversation so far (my own interview)",
    description="Questions, answers, code and notes in order — so a reloaded page can show where the interview is. Never the evaluation.",
    responses=errors(*AUTHENTICATED),
)
async def get_my_transcript(interview_id: InterviewIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> TranscriptResponse:
    service = InterviewService(db, settings)
    interview = await service.get_mine(auth.user_id, interview_id)
    return TranscriptResponse(message="", turns=[turn_out(t) for t in await service.turns(interview)])


@router.get("/{interview_id}/consent", response_model=ConsentResponse, summary="What to read and agree to before starting", responses=errors(*AUTHENTICATED))
async def get_consent(interview_id: InterviewIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ConsentResponse:
    service = InterviewService(db, settings)
    interview = await service.get_mine(auth.user_id, interview_id)
    return ConsentResponse(message="", consent=ConsentOut(**service.consent_info(interview)))


@router.post("/{interview_id}/consent", response_model=InterviewResponse, summary="Accept the consent", responses=errors(*AUTHENTICATED, 409), dependencies=[WriteRateLimit])
async def accept_consent(interview_id: InterviewIdParam, body: ConsentRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> InterviewResponse:
    service = InterviewService(db, settings)
    interview = await service.consent(await service.get_mine(auth.user_id, interview_id), version=body.version, recording=body.recording)
    return InterviewResponse(message="Consent recorded: start when you are ready.", interview=interview_out(interview))


@router.post(
    "/{interview_id}/start", response_model=TurnResponse, summary="Start the interview", responses=errors(*AUTHENTICATED, 409),
    description="The clock starts now, by the server: nothing the candidate's device sends can move it.", dependencies=[WriteRateLimit],
)
async def start_interview(interview_id: InterviewIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> TurnResponse:
    service = InterviewService(db, settings)
    interview, opening = await service.start(await service.get_mine(auth.user_id, interview_id))
    return TurnResponse(message="Interview started.", turns=TurnPair(turn=turn_out(opening), reply=None, finished=False, degraded=False))


@router.post(
    "/{interview_id}/turns", response_model=TurnResponse, summary="Answer (typed)", responses=errors(*AUTHENTICATED, 409, 429, 503),
    description="Send your answer; the interviewer's reply is either a follow-up the AI proposed or the next core question, decided by the director, "
    "never by the model directly. Retried with the same Idempotency-Key returns the same result.", dependencies=[TurnRateLimit],
)
async def answer_turn(
    interview_id: InterviewIdParam, body: AnswerText, auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep, idempotency_key: IdempotencyKeyHeader
) -> TurnResponse:
    interview = await InterviewService(db, settings).get_mine(auth.user_id, interview_id)
    turn, reply, _, extras = await ConductService(db, settings, gateway).answer(interview, text=body.text, audio=None, audio_type=None, key=idempotency_key, want_audio=body.want_audio)
    return _turn_response(turn, reply, extras)


@router.post(
    "/{interview_id}/turns/audio", response_model=TurnResponse, summary="Answer (spoken)", responses=errors(*AUTHENTICATED, 409, 429, 503),
    description="Multipart form: the recorded answer. Speech is best effort — if it is not configured or transcription fails, type the answer instead.",
    dependencies=[TurnRateLimit],
)
async def answer_turn_audio(
    interview_id: InterviewIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep, gateway: GatewayDep, idempotency_key: IdempotencyKeyHeader,
    audio: UploadFile = File(...), want_audio: Annotated[bool, Form()] = False,
) -> TurnResponse:
    content = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(content) > MAX_AUDIO_BYTES:
        raise ValidationFailedError(details=[{"field": "audio", "code": "TOO_LARGE", "message": "Keep a recorded answer under 15 MB"}])
    if not content:
        raise ValidationFailedError(details=[{"field": "audio", "code": "REQUIRED", "message": "Attach a recording"}])
    interview = await InterviewService(db, settings).get_mine(auth.user_id, interview_id)
    turn, reply, _, extras = await ConductService(db, settings, gateway).answer(
        interview, text=None, audio=content, audio_type=audio.content_type, key=idempotency_key, want_audio=want_audio
    )
    return _turn_response(turn, reply, extras)


def _turn_response(turn: InterviewTurn, reply: InterviewTurn | None, extras: dict[str, object]) -> TurnResponse:
    reply_out = turn_out(reply) if reply is not None else None
    pair = TurnPair(
        turn=turn_out(turn), reply=reply_out, finished=bool(extras.get("finished") or extras.get("ended") or extras.get("replayed")), degraded=bool(extras.get("degraded")),
        audio=extras.get("audio"), audio_type=extras.get("audio_type"), audio_error=extras.get("audio_error"),
    )
    return TurnResponse(message="", turns=pair)


@router.post(
    "/{interview_id}/code/run", response_model=CodeRunResponse, summary="Run code (coding round)", responses=errors(*AUTHENTICATED, 409, 429, 503), dependencies=[TurnRateLimit],
)
async def run_code(interview_id: InterviewIdParam, body: CodeRunRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep, codeexec: CodeExecDep) -> CodeRunResponse:
    interview = await InterviewService(db, settings).get_mine(auth.user_id, interview_id)
    code_turn, result_turn, result = await ConductService(db, settings, None, codeexec).run_code(interview, language=body.language, source=body.source, stdin=body.stdin)
    return CodeRunResponse(
        message="", run=CodeRunOut(
            code=turn_out(code_turn), result=turn_out(result_turn), run_id=result["run_id"], status=result["status"], outcome=result["outcome"], stdout=result["stdout"],
            stderr=result["stderr"], compile_output=result["compile_output"], time_ms=result["time_ms"],
        )
    )


@router.post("/{interview_id}/end", response_model=InterviewResponse, summary="End the interview early", responses=errors(*AUTHENTICATED, 409), dependencies=[WriteRateLimit])
async def end_interview(interview_id: InterviewIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> InterviewResponse:
    service = InterviewService(db, settings)
    interview = await service.end(await service.get_mine(auth.user_id, interview_id))
    return InterviewResponse(message="Interview ended: it will be scored shortly.", interview=interview_out(interview))


@router.get("/{interview_id}/time-left", response_model=TimeLeftOut, summary="Seconds left, by the server's clock", responses=errors(*AUTHENTICATED))
async def time_left(interview_id: InterviewIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> TimeLeftOut:
    service = InterviewService(db, settings)
    interview = await service.get_mine(auth.user_id, interview_id)
    round_left, total_left = service.seconds_left(interview) if interview.status == InterviewStatus.IN_PROGRESS else (0.0, 0.0)
    return TimeLeftOut(round_seconds_left=max(int(round_left), 0), interview_seconds_left=max(int(total_left), 0))


@router.get("/{interview_id}/report", response_model=ReportResponse, summary="My report", responses=errors(*AUTHENTICATED))
async def get_report(interview_id: InterviewIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> ReportResponse:
    interview = await InterviewService(db, settings).get_mine(auth.user_id, interview_id)
    evaluation = await EvaluationService(db, settings, None).for_interview(interview)
    return ReportResponse(message="", report=report_out(interview, evaluation))


@router.post(
    "/{interview_id}/appeal", response_model=AppealResponse, status_code=201, summary="Appeal a hiring result", responses=errors(*AUTHENTICATED, 403, 409), dependencies=[WriteRateLimit],
)
async def appeal_interview(interview_id: InterviewIdParam, body: AppealRequest, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> AppealResponse:
    interview = await InterviewService(db, settings).get_mine(auth.user_id, interview_id)
    appeal = await ReviewService(db, settings).appeal(auth.user_id, interview, body.reason)
    return AppealResponse(message="Appeal submitted: a different reviewer will decide it.", appeal=appeal_out(appeal, interview.public_id))


@router.post("/{interview_id}/retake", response_model=InterviewResponse, status_code=201, summary="Take the fresh attempt an upheld appeal granted", responses=errors(*AUTHENTICATED, 403, 409))
async def retake_interview(interview_id: InterviewIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep) -> InterviewResponse:
    service = InterviewService(db, settings)
    fresh = await service.retake(auth, await service.get_mine(auth.user_id, interview_id))
    return InterviewResponse(message="A new interview has been created for your retake.", interview=interview_out(fresh))
