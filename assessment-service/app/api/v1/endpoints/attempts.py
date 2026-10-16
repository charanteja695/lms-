from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder
from sqlalchemy import select

from app.api.deps import (
    AnswerSaveRateLimit,
    AttemptCreateRateLimit,
    AttemptIdParam,
    CurrentAuth,
    DbSession,
    FileUrlRateLimit,
    IdempotencyKeyHeader,
    QuestionIdParam,
    RedisDep,
    RequestCtx,
    RequireStudent,
    SettingsDep,
    TestIdParam,
)
from app.api.responses import AUTHENTICATED, errors
from app.api.views import paper_view, result_view, state_of
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.time import utcnow
from app.domain.enums import SubmitReason
from app.models.attempt import Attempt, AttemptEvent
from app.permissions.policy import can_grade_attempt, can_view_attempt
from app.schemas.attempt import (
    AnswerBatchIn,
    AnswerIn,
    AttemptCreate,
    AttemptEventOut,
    AttemptEventsResponse,
    AttemptListItem,
    AttemptListResponse,
    AttemptPaperResponse,
    AttemptResponse,
    FileDownloadOut,
    FileDownloadResponse,
    FileUploadOut,
    FileUploadResponse,
    FileUploadUrlIn,
    ReasonIn,
    ResultResponse,
    ResultsRowOut,
    ResultsSummaryRequest,
    ResultsSummaryResponse,
    ResultsTestOut,
    SavedAnswerOut,
    SavedAnswersResponse,
)
from app.schemas.common import AttemptQuery
from app.services.answer_service import AnswerItem, AnswerService
from app.services.attempt_service import AttemptService
from app.services.file_service import FileService
from app.services.grading_service import GradingService
from app.services.report_service import ReportService
from app.services.test_service import TestService

router = APIRouter(tags=["Attempts"])


async def _viewable(service: AttemptService, public_id: int, auth) -> Attempt:  # type: ignore[no-untyped-def]
    """The attempt, if the caller may see it; not-found otherwise (an id must not confirm someone else's attempt)."""
    attempt = await service.get(public_id)
    test = await service.test_of(attempt)
    if not can_view_attempt(auth, attempt_user_id=attempt.user_id, attempt_organization_id=attempt.organization_id, test_owner_id=test.organization_id):
        raise NotFoundError("Attempt not found.", code="ATTEMPT_NOT_FOUND")
    return attempt


async def _controllable(service: AttemptService, public_id: int, auth) -> Attempt:  # type: ignore[no-untyped-def]
    attempt = await _viewable(service, public_id, auth)
    test = await service.test_of(attempt)
    if attempt.user_id == auth.user_id or not can_grade_attempt(auth, attempt_organization_id=attempt.organization_id, test_owner_id=test.organization_id):
        raise PermissionDeniedError()
    return attempt


# ------------------------------------------------------------------ taking a test


@router.post(
    "/tests/{test_id}/attempts",
    response_model=AttemptResponse,
    status_code=201,
    dependencies=[AttemptCreateRateLimit],
    summary="Prepare (and optionally start) an attempt",
    description="Checks enrolment/eligibility, attempts left, cooldown and the exam window, then prepares this student's "
    "paper (the waiting room): the clock does not run and no attempt is used until the attempt is started. Returns the "
    "attempt already open for this test if there is one. `start_now` also starts it. Send an Idempotency-Key.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def create_attempt(
    test_id: TestIdParam,
    data: AttemptCreate,
    auth: RequireStudent,
    db: DbSession,
    settings: SettingsDep,
    redis: RedisDep,
    ctx: RequestCtx,
    key: IdempotencyKeyHeader,
) -> AttemptResponse:
    test = await TestService(db, settings, redis).load(test_id)
    service = AttemptService(db, settings, redis)
    attempt = await service.prepare(test, auth, ctx, key=key)
    if data.start_now:
        attempt = await service.start(attempt, auth, ctx)
    return AttemptResponse(message="Attempt ready.", attempt=await state_of(service, attempt, test))


@router.post(
    "/attempts/{attempt_id}/start",
    response_model=AttemptPaperResponse,
    dependencies=[AttemptCreateRateLimit],
    summary="Start the clock and get the paper",
    description="Admitted staggered when an exam opens (429 `WAITING_ROOM` with `Retry-After`: retry after that many "
    "seconds). Starting a running attempt is a resume.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def start_attempt(attempt_id: AttemptIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep, ctx: RequestCtx) -> AttemptPaperResponse:
    service = AttemptService(db, settings, redis)
    attempt = await service.start(await service.get_owned(attempt_id, auth.user_id), auth, ctx)
    test = await service.test_of(attempt, with_sections=True)
    questions = await paper_view(db, service, AnswerService(db, settings, redis), attempt, test)
    return AttemptPaperResponse(message="Attempt started.", attempt=await state_of(service, attempt, test), questions=questions)


@router.post(
    "/attempts/{attempt_id}/resume",
    response_model=AttemptPaperResponse,
    summary="Re-open a running attempt",
    description="Call this when the page is reloaded or the device restarted: returns the paper with the answers saved "
    "so far and the time left. Each resume is logged.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def resume_attempt(attempt_id: AttemptIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep, ctx: RequestCtx) -> AttemptPaperResponse:
    service = AttemptService(db, settings, redis)
    attempt = await service.resume(await service.get_owned(attempt_id, auth.user_id), auth, ctx)
    test = await service.test_of(attempt, with_sections=True)
    questions = await paper_view(db, service, AnswerService(db, settings, redis), attempt, test)
    return AttemptPaperResponse(message="Attempt resumed.", attempt=await state_of(service, attempt, test), questions=questions)


@router.get(
    "/attempts/{attempt_id}",
    response_model=AttemptPaperResponse,
    summary="The attempt's state (and the paper while it runs)",
    description="`remaining_seconds` is computed by the server, whose clock is the authority. Once the attempt has ended "
    "this returns the state only; results come from GET /attempts/{id}/result.",
    responses=errors(*AUTHENTICATED, 404),
)
async def get_attempt(attempt_id: AttemptIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep) -> AttemptPaperResponse:
    service = AttemptService(db, settings, redis)
    attempt = await service.refresh(await _viewable(service, attempt_id, auth))
    test = await service.test_of(attempt, with_sections=True)
    questions = []
    if attempt.user_id == auth.user_id:
        questions = await paper_view(db, service, AnswerService(db, settings, redis), attempt, test)
    return AttemptPaperResponse(message="Attempt retrieved successfully.", attempt=await state_of(service, attempt, test), questions=questions)


def _saved(results, now) -> SavedAnswersResponse:  # type: ignore[no-untyped-def]
    return SavedAnswersResponse(
        message="Answers saved.",
        answers=[SavedAnswerOut(question_id=r.question_id, status=r.status, revision=r.revision, error=r.error) for r in results],
        server_time=now,
    )


@router.put(
    "/attempts/{attempt_id}/answers/{question_id}",
    response_model=SavedAnswersResponse,
    dependencies=[AnswerSaveRateLimit],
    summary="Save one answer (autosave)",
    description="Built for a save on every change: the answer goes to Redis and is flushed to the database in batches. "
    "`revision` is the client's change counter; an older revision never overwrites a newer one (`status: stale`). "
    "A null/empty `response` clears the answer. 409 `ATTEMPT_ENDED` once time is up.",
    responses=errors(*AUTHENTICATED, 404, 409, 422),
)
async def save_answer(
    attempt_id: AttemptIdParam, question_id: QuestionIdParam, data: AnswerIn, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> SavedAnswersResponse:
    results = await AnswerService(db, settings, redis).save(auth.user_id, attempt_id, [AnswerItem(question_id, data.response, data.revision, data.flagged)])
    if results[0].status == "rejected":
        from app.core.exceptions import ValidationFailedError

        error = results[0].error or {}
        raise ValidationFailedError(details=[{"field": "response", "code": error.get("code", "INVALID_ANSWER"), "message": error.get("message", "The answer is not valid")}])
    return _saved(results, utcnow())


@router.put(
    "/attempts/{attempt_id}/answers",
    response_model=SavedAnswersResponse,
    dependencies=[AnswerSaveRateLimit],
    summary="Save several answers at once",
    description="For a client flushing its local buffer after a network drop. Each answer succeeds or is rejected on its "
    "own; the response reports each.",
    responses=errors(*AUTHENTICATED, 404, 409, 422),
)
async def save_answers(attempt_id: AttemptIdParam, data: AnswerBatchIn, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep) -> SavedAnswersResponse:
    items = [AnswerItem(item.question_id, item.response, item.revision, item.flagged) for item in data.answers]
    return _saved(await AnswerService(db, settings, redis).save(auth.user_id, attempt_id, items), utcnow())


@router.post(
    "/attempts/{attempt_id}/answers/{question_id}/file-upload-url",
    response_model=FileUploadResponse,
    dependencies=[FileUrlRateLimit],
    summary="Get a presigned upload for a file answer",
    description="Upload the file directly to `upload.url` with `upload.fields` (a multipart POST), then save the answer "
    "with `{\"files\": [{\"key\", \"filename\", \"size\", \"content_type\"}]}`.",
    responses=errors(*AUTHENTICATED, 404, 409, 422),
)
async def file_upload_url(
    attempt_id: AttemptIdParam, question_id: QuestionIdParam, data: FileUploadUrlIn, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> FileUploadResponse:
    upload = await FileService(db, settings, redis).upload_url(
        auth.user_id, attempt_id, question_id, filename=data.filename, content_type=data.content_type, size_bytes=data.size_bytes
    )
    return FileUploadResponse(message="Upload URL issued.", file=FileUploadOut(**upload))


@router.post(
    "/attempts/{attempt_id}/finish-section",
    response_model=AttemptResponse,
    summary="Finish the current section (per-section tests)",
    description="Locks the section you are in and starts the next one. Finishing the last section submits the attempt.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def finish_section(attempt_id: AttemptIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep) -> AttemptResponse:
    service = AttemptService(db, settings, redis)
    attempt = await service.finish_section(await service.get_owned(attempt_id, auth.user_id), auth)
    return AttemptResponse(message="Section finished.", attempt=await state_of(service, attempt))


@router.post(
    "/attempts/{attempt_id}/submit",
    response_model=AttemptResponse,
    status_code=202,
    summary="Submit the attempt",
    description="Ends the attempt and queues it for grading; returns at once. Submitting twice is not an error. Poll "
    "GET /attempts/{id}/result for the outcome.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def submit_attempt(attempt_id: AttemptIdParam, auth: RequireStudent, db: DbSession, settings: SettingsDep, redis: RedisDep, ctx: RequestCtx) -> AttemptResponse:
    service = AttemptService(db, settings, redis)
    attempt = await service.submit(await service.get_owned(attempt_id, auth.user_id), reason=SubmitReason.MANUAL, ip_address=ctx.ip_address)
    return AttemptResponse(message="Attempt submitted; it is being graded.", attempt=await state_of(service, attempt))


@router.get(
    "/attempts/{attempt_id}/result",
    response_model=ResultResponse,
    summary="The result of an attempt",
    description="Before grading finishes or before the result is released the student gets a status message only. Once "
    "released: score, pass/fail and — if the test's review policy is `answers` — each question with the correct answer "
    "and explanation. Staff, exam managers and the owning employer see everything, including grader feedback.",
    responses=errors(*AUTHENTICATED, 404),
)
async def get_result(attempt_id: AttemptIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep) -> ResultResponse:
    service = AttemptService(db, settings, redis)
    attempt = await _viewable(service, attempt_id, auth)
    test = await service.test_of(attempt)
    return ResultResponse(message="Result retrieved successfully.", result=await result_view(db, service, AnswerService(db, settings, redis), attempt, test, auth))


# ------------------------------------------------------------------ lists and history


@router.get(
    "/attempts",
    response_model=AttemptListResponse,
    summary="List attempts",
    description="Students: their own. Exam managers: all. Institution staff: their students' (platform tests). Employers: attempts on their hiring tests.",
    responses=errors(*AUTHENTICATED),
)
async def list_attempts(query: Annotated[AttemptQuery, Query()], auth: CurrentAuth, db: DbSession) -> AttemptListResponse:
    attempts, total, is_exact = await ReportService(db).list_attempts(query, auth)
    return AttemptListResponse(
        message="Attempts retrieved successfully.",
        attempts=[AttemptListItem.model_validate(a) for a in attempts],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.post(
    "/results/summary",
    response_model=ResultsSummaryResponse,
    summary="Marks and results for a group of students",
    description="Per student and test: attempts, best score and whether they passed. Institution staff and heads see their own students "
    "(platform tests); exam managers see anyone. Send a section's roster as `user_ids`.",
    responses=errors(*AUTHENTICATED, 422),
)
async def results_summary(body: ResultsSummaryRequest, auth: CurrentAuth, db: DbSession) -> ResultsSummaryResponse:
    tests, rows = await ReportService(db).results_summary(auth, body.user_ids, body.test_id)
    return ResultsSummaryResponse(
        message="Results retrieved successfully.",
        tests=[ResultsTestOut(test_id=t.public_id, title=t.title, kind=t.kind, pass_mark_percent=t.pass_mark_percent) for t in tests],
        rows=[ResultsRowOut.model_validate(r) for r in rows],
    )


@router.get("/attempts/{attempt_id}/events", response_model=AttemptEventsResponse, summary="The attempt's audit trail (staff)", responses=errors(*AUTHENTICATED, 404))
async def attempt_events(attempt_id: AttemptIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep) -> AttemptEventsResponse:
    service = AttemptService(db, settings, redis)
    attempt = await _viewable(service, attempt_id, auth)
    if attempt.user_id == auth.user_id:
        raise PermissionDeniedError()
    rows = (await db.execute(select(AttemptEvent).where(AttemptEvent.attempt_id == attempt.id).order_by(AttemptEvent.created_at))).scalars()
    return AttemptEventsResponse(message="Events retrieved successfully.", events=[AttemptEventOut.model_validate(e) for e in rows])


# ------------------------------------------------------------------ live control and regrading (staff)


@router.post("/attempts/{attempt_id}/pause", response_model=AttemptResponse, summary="Pause a running attempt (stops the clock)", responses=errors(*AUTHENTICATED, 403, 404, 409))
async def pause_attempt(attempt_id: AttemptIdParam, data: ReasonIn, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep) -> AttemptResponse:
    service = AttemptService(db, settings, redis)
    attempt = await service.pause(await _controllable(service, attempt_id, auth), auth.user_id, data.reason)
    return AttemptResponse(message="Attempt paused.", attempt=await state_of(service, attempt))


@router.post("/attempts/{attempt_id}/unpause", response_model=AttemptResponse, summary="Resume a paused attempt (the stopped time is given back)", responses=errors(*AUTHENTICATED, 403, 404, 409))
async def unpause_attempt(attempt_id: AttemptIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep) -> AttemptResponse:
    service = AttemptService(db, settings, redis)
    attempt = await service.unpause(await _controllable(service, attempt_id, auth), auth.user_id)
    return AttemptResponse(message="Attempt resumed.", attempt=await state_of(service, attempt))


@router.post("/attempts/{attempt_id}/terminate", response_model=AttemptResponse, summary="End an attempt now (submitted as it stands)", responses=errors(*AUTHENTICATED, 403, 404, 409))
async def terminate_attempt(attempt_id: AttemptIdParam, data: ReasonIn, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep, ctx: RequestCtx) -> AttemptResponse:
    service = AttemptService(db, settings, redis)
    attempt = await service.terminate(await _controllable(service, attempt_id, auth), auth.user_id, data.reason, ctx.ip_address)
    return AttemptResponse(message="Attempt terminated.", attempt=await state_of(service, attempt))


@router.post(
    "/attempts/{attempt_id}/regrade",
    response_model=AttemptResponse,
    summary="Recompute an attempt's grades",
    description="Automatic grades are recomputed from the pinned question versions; human grades are kept. If the "
    "outcome changed after release it is announced again with a higher revision. Exam managers only.",
    responses=errors(*AUTHENTICATED, 403, 404, 409),
)
async def regrade_attempt(attempt_id: AttemptIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep) -> AttemptResponse:
    from app.permissions.policy import can_manage_exams

    if not can_manage_exams(auth):
        raise PermissionDeniedError()
    service = AttemptService(db, settings, redis)
    attempt = await GradingService(db, settings, redis).regrade(attempt_id, auth)
    return AttemptResponse(message="Attempt regraded.", attempt=await state_of(service, attempt))


@router.get(
    "/attempts/{attempt_id}/answers/{question_id}/files/{index}",
    response_model=FileDownloadResponse,
    summary="A short-lived download link for a file answer (graders)",
    responses=errors(*AUTHENTICATED, 403, 404),
)
async def download_answer_file(
    attempt_id: AttemptIdParam, question_id: QuestionIdParam, index: int, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> FileDownloadResponse:
    download = await FileService(db, settings, redis).download_url(auth, attempt_id, question_id, index)
    return FileDownloadResponse(message="Download link issued.", file=FileDownloadOut(**download))
