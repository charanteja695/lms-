from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    AuthoringRateLimit,
    CurrentAuth,
    DbSession,
    IdempotencyKeyHeader,
    RedisDep,
    RequireAuthor,
    ScheduleIdParam,
    SettingsDep,
    TestIdParam,
)
from app.api.presenters import definition_out
from app.api.responses import AUTHENTICATED, errors
from app.core.exceptions import PermissionDeniedError
from app.core.security import AccessTokenClaims
from app.models.test import Test, TestSchedule
from app.permissions.policy import can_manage_owned_by
from app.schemas.attempt import (
    AttemptListItem,
    AttemptListResponse,
    PlagiarismItem,
    PlagiarismResponse,
    ReleaseResultsResponse,
    TestAnalyticsOut,
    TestAnalyticsResponse,
)
from app.schemas.common import AttemptQuery, TestQuery
from app.schemas.question import RejectNote, ReviewNote
from app.schemas.test import (
    CompositionRequest,
    CompositionResponse,
    ScheduleCreate,
    ScheduleListResponse,
    ScheduleOut,
    ScheduleResponse,
    ScheduleUpdate,
    SectionsReplace,
    TestComposition,
    TestCompositionItem,
    TestCreate,
    TestIssue,
    TestListItem,
    TestListResponse,
    TestResponse,
    TestUpdate,
    TestValidationResponse,
)
from app.services.report_service import ReportService, export_results_csv
from app.services.result_service import ResultService
from app.services.schedule_service import ScheduleService
from app.services.test_service import TestService

router = APIRouter(prefix="/tests", tags=["Tests"])


async def _test_response(service: TestService, test: Test, message: str) -> TestResponse:
    return TestResponse(message=message, test=definition_out(test, await service.question_public_ids(test)))


def _schedule_out(schedule: TestSchedule, test: Test) -> ScheduleOut:
    return ScheduleOut(
        public_id=schedule.public_id,
        test_id=test.public_id,
        title=schedule.title,
        organization_id=schedule.organization_id,
        starts_at=schedule.starts_at,
        ends_at=schedule.ends_at,
        enforce_end=schedule.enforce_end,
        results_release_at=schedule.results_release_at,
        cancelled_at=schedule.cancelled_at,
        created_at=schedule.created_at,
    )


# ------------------------------------------------------------------ authoring


@router.post(
    "",
    response_model=TestResponse,
    status_code=201,
    dependencies=[AuthoringRateLimit],
    summary="Create a test (draft)",
    description="`kind` is topic, module, final, practice or hiring. Topic, module and final tests name their catalog "
    "`target_id`. Sections can be given now or set later with PUT /tests/{id}/sections. Employers can only create hiring tests.",
    responses=errors(*AUTHENTICATED, 409),
)
async def create_test(data: TestCreate, auth: RequireAuthor, db: DbSession, settings: SettingsDep, redis: RedisDep, key: IdempotencyKeyHeader) -> TestResponse:
    service = TestService(db, settings, redis)
    return await _test_response(service, await service.create(data, auth, key), "Test created successfully.")


@router.get("", response_model=TestListResponse, summary="List tests (authors, reviewers, exam managers)", responses=errors(*AUTHENTICATED))
async def list_tests(query: Annotated[TestQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TestListResponse:
    tests, total, is_exact = await TestService(db, settings).list_tests(query, auth)
    return TestListResponse(
        message="Tests retrieved successfully.",
        tests=[TestListItem.model_validate(test) for test in tests],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.post(
    "/compositions",
    response_model=CompositionResponse,
    summary="What several tests hold (multiple choice, programs) against what they need",
    description="For a course builder: one call for every topic test of a course. Only tests the caller may read.",
    responses=errors(*AUTHENTICATED, 404, 422),
)
async def test_compositions(data: CompositionRequest, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> CompositionResponse:
    service = TestService(db, settings)
    items: list[TestCompositionItem] = []
    for test_id in dict.fromkeys(data.test_ids):  # keep order, drop repeats
        issues, _total, _count, composition = await service.validate_with_composition(await service.get(test_id, auth))
        items.append(TestCompositionItem(test_id=str(test_id), valid=not issues, issue_count=len(issues), **composition))
    return CompositionResponse(message="Compositions retrieved successfully.", compositions=items)


@router.get("/{test_id}", response_model=TestResponse, summary="Get a test definition", responses=errors(*AUTHENTICATED, 404))
async def get_test(test_id: TestIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TestResponse:
    service = TestService(db, settings)
    return await _test_response(service, await service.get(test_id, auth), "Test retrieved successfully.")


@router.patch("/{test_id}", response_model=TestResponse, dependencies=[AuthoringRateLimit], summary="Edit a draft test", responses=errors(*AUTHENTICATED, 404, 409))
async def update_test(test_id: TestIdParam, data: TestUpdate, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TestResponse:
    service = TestService(db, settings)
    return await _test_response(service, await service.update(await service.get(test_id, auth), data, auth), "Test updated successfully.")


@router.put(
    "/{test_id}/sections",
    response_model=TestResponse,
    dependencies=[AuthoringRateLimit],
    summary="Replace the sections and slots of a draft test",
    description="Sets the whole structure in one call. A slot is a `fixed` question or a `pool` drawn per student from "
    "questions matching the criteria (any-of within skills/topics/tags/bloom/types, all kinds must match).",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def replace_sections(test_id: TestIdParam, data: SectionsReplace, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TestResponse:
    service = TestService(db, settings)
    return await _test_response(service, await service.replace_sections(await service.get(test_id, auth), data.sections, auth), "Sections saved successfully.")


@router.delete("/{test_id}", response_model=TestResponse, summary="Delete a draft test", responses=errors(*AUTHENTICATED, 404, 409))
async def delete_test(test_id: TestIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TestResponse:
    service = TestService(db, settings)
    test = await service.get(test_id, auth)
    response = await _test_response(service, test, "Test deleted successfully.")
    await service.delete_draft(test, auth)
    return response


@router.get(
    "/{test_id}/validation",
    response_model=TestValidationResponse,
    summary="Check whether a test is ready to publish",
    description="Lists everything that would stop it being submitted: missing timing, unavailable questions, pools too small to draw from.",
    responses=errors(*AUTHENTICATED, 404),
)
async def validate_test(test_id: TestIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TestValidationResponse:
    service = TestService(db, settings)
    issues, total, count, composition = await service.validate_with_composition(await service.get(test_id, auth))
    return TestValidationResponse(
        message="Test is ready." if not issues else "Test has issues.",
        valid=not issues,
        issues=[TestIssue(**issue) for issue in issues],
        total_marks=total,
        question_count=count,
        composition=TestComposition(**composition),
    )


@router.post("/{test_id}/submit", response_model=TestResponse, summary="Submit a draft for review", responses=errors(*AUTHENTICATED, 404, 409, 422))
async def submit_test(test_id: TestIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TestResponse:
    service = TestService(db, settings)
    return await _test_response(service, await service.submit(await service.get(test_id, auth), auth), "Test submitted for review.")


@router.post(
    "/{test_id}/approve",
    response_model=TestResponse,
    summary="Approve and publish a test",
    description="Freezes the test and emits `test.published` (catalog-service attaches it to its module/topic). "
    "Needs `content.review` and someone other than the author.",
    responses=errors(*AUTHENTICATED, 404, 409, 422),
)
async def approve_test(test_id: TestIdParam, data: ReviewNote, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TestResponse:
    service = TestService(db, settings)
    return await _test_response(service, await service.approve(await service.get(test_id, auth), auth, data.note), "Test approved and published.")


@router.post("/{test_id}/reject", response_model=TestResponse, summary="Send a test in review back to draft", responses=errors(*AUTHENTICATED, 404, 409))
async def reject_test(test_id: TestIdParam, data: RejectNote, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TestResponse:
    service = TestService(db, settings)
    return await _test_response(service, await service.reject(await service.get(test_id, auth), auth, data.note), "Test sent back to draft.")


@router.post("/{test_id}/retire", response_model=TestResponse, summary="Retire a published test", responses=errors(*AUTHENTICATED, 404, 409))
async def retire_test(test_id: TestIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TestResponse:
    service = TestService(db, settings)
    return await _test_response(service, await service.retire(await service.get(test_id, auth), auth), "Test retired.")


@router.post("/{test_id}/clone", response_model=TestResponse, status_code=201, summary="Copy a test into a new draft", responses=errors(*AUTHENTICATED, 404))
async def clone_test(test_id: TestIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TestResponse:
    service = TestService(db, settings)
    return await _test_response(service, await service.clone(await service.get(test_id, auth), auth), "Test cloned into a new draft.")


# ------------------------------------------------------------------ schedules


@router.get("/{test_id}/schedules", response_model=ScheduleListResponse, summary="Exam windows of a test", responses=errors(*AUTHENTICATED, 404))
async def list_schedules(test_id: TestIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> ScheduleListResponse:
    test = await TestService(db, settings).get(test_id, auth)
    schedules = await ScheduleService(db).list_for(test)
    return ScheduleListResponse(message="Schedules retrieved successfully.", schedules=[_schedule_out(s, test) for s in schedules])


@router.post(
    "/{test_id}/schedules",
    response_model=ScheduleResponse,
    status_code=201,
    summary="Schedule an exam window",
    description="Students prepare their paper in the waiting room before `starts_at` and are admitted, staggered, once "
    "it opens. `organization_id` limits the session to one institution. Needs `exams.manage`.",
    responses=errors(*AUTHENTICATED, 404, 409),
)
async def create_schedule(test_id: TestIdParam, data: ScheduleCreate, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> ScheduleResponse:
    test = await TestService(db, settings).get(test_id, auth)
    schedule = await ScheduleService(db).create(test, data, auth)
    return ScheduleResponse(message="Schedule created successfully.", schedule=_schedule_out(schedule, test))


@router.patch("/{test_id}/schedules/{schedule_id}", response_model=ScheduleResponse, summary="Change an exam window", responses=errors(*AUTHENTICATED, 404, 409))
async def update_schedule(
    test_id: TestIdParam, schedule_id: ScheduleIdParam, data: ScheduleUpdate, auth: CurrentAuth, db: DbSession, settings: SettingsDep
) -> ScheduleResponse:
    test = await TestService(db, settings).get(test_id, auth)
    service = ScheduleService(db)
    schedule = await service.update(test, await service.get(schedule_id, test), data, auth)
    return ScheduleResponse(message="Schedule updated successfully.", schedule=_schedule_out(schedule, test))


@router.delete("/{test_id}/schedules/{schedule_id}", response_model=ScheduleResponse, summary="Cancel an exam window", responses=errors(*AUTHENTICATED, 404))
async def cancel_schedule(test_id: TestIdParam, schedule_id: ScheduleIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> ScheduleResponse:
    test = await TestService(db, settings).get(test_id, auth)
    service = ScheduleService(db)
    schedule = await service.cancel(test, await service.get(schedule_id, test), auth)
    return ScheduleResponse(message="Schedule cancelled.", schedule=_schedule_out(schedule, test))


# ------------------------------------------------------------------ results and reports


def _require_manager(test: Test, auth: AccessTokenClaims) -> None:
    if not can_manage_owned_by(auth, test.organization_id):
        raise PermissionDeniedError()


@router.get(
    "/{test_id}/results",
    response_model=AttemptListResponse,
    summary="Attempts and results of a test",
    description="Exam managers see every attempt; an institution's staff see their own students' (platform tests); an "
    "employer sees attempts on its hiring tests.",
    responses=errors(*AUTHENTICATED, 404),
)
async def test_results(
    test_id: TestIdParam, query: Annotated[AttemptQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep
) -> AttemptListResponse:
    test = await TestService(db, settings).load(test_id)
    attempts, total, is_exact = await ReportService(db).list_attempts(query, auth, test_public_id=test.public_id)
    return AttemptListResponse(
        message="Results retrieved successfully.",
        attempts=[AttemptListItem.model_validate(a) for a in attempts],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get(
    "/{test_id}/results/export",
    summary="Download the results of a test as CSV",
    description="Streamed page by page, so an exam of any size downloads in constant memory.",
    responses={**errors(*AUTHENTICATED, 404), 200: {"content": {"text/csv": {}}, "description": "CSV"}},
)
async def export_results(test_id: TestIdParam, request: Request, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> StreamingResponse:
    test = await TestService(db, settings).load(test_id)
    _require_manager(test, auth)
    return StreamingResponse(
        export_results_csv(request.app.state.sessionmaker, test.id),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="results-{test.public_id}.csv"'},
    )


@router.get("/{test_id}/analytics", response_model=TestAnalyticsResponse, summary="Pass rate, score distribution and question statistics", responses=errors(*AUTHENTICATED, 404))
async def test_analytics(test_id: TestIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> TestAnalyticsResponse:
    test = await TestService(db, settings).load(test_id)
    _require_manager(test, auth)
    return TestAnalyticsResponse(message="Analytics retrieved successfully.", analytics=TestAnalyticsOut(**await ReportService(db).analytics(test)))


@router.get(
    "/{test_id}/plagiarism",
    response_model=PlagiarismResponse,
    summary="Coding answers flagged for high similarity",
    description="From code-execution-service's token-fingerprint comparison across submissions. A flag is a signal for "
    "a reviewer, never a verdict.",
    responses=errors(*AUTHENTICATED, 404),
)
async def test_plagiarism(test_id: TestIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep) -> PlagiarismResponse:
    test = await TestService(db, settings).load(test_id)
    _require_manager(test, auth)
    return PlagiarismResponse(message="Plagiarism report retrieved successfully.", flagged=[PlagiarismItem(**row) for row in await ReportService(db).plagiarism(test)])


@router.post(
    "/{test_id}/release-results",
    response_model=ReleaseResultsResponse,
    summary="Release the results of a test",
    description="For tests whose `result_visibility` is `manual` (or to release an `after_window` test early): every "
    "decided, unreleased attempt becomes visible to its student and is announced to the rest of the platform.",
    responses=errors(*AUTHENTICATED, 404),
)
async def release_results(test_id: TestIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep) -> ReleaseResultsResponse:
    test = await TestService(db, settings).load(test_id)
    _require_manager(test, auth)
    scheduled = await ResultService(db, settings, redis).release_test(test)
    return ReleaseResultsResponse(message="Results are being released.", scheduled=scheduled)
