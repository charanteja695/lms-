from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    AuthoringRateLimit,
    CipherDep,
    CurrentAuth,
    DbSession,
    ProblemIdParam,
    RequireAuthor,
    RequireReviewer,
    SettingsDep,
)
from app.api.presenters import problem_author_out, problem_list_item, problem_out
from app.api.responses import AUTHENTICATED, errors
from app.permissions.policy import can_review
from app.schemas.common import ProblemQuery
from app.schemas.problem import (
    ProblemAuthorResponse,
    ProblemCreate,
    ProblemListResponse,
    ProblemResponse,
    ProblemStatsOut,
    ProblemStatsResponse,
    ProblemUpdate,
)
from app.services.language_service import LanguageService
from app.services.problem_service import ProblemService
from app.services.test_case_service import TestCaseService

router = APIRouter(prefix="/problems", tags=["Problems"])


@router.get("", response_model=ProblemListResponse, summary="List problems", responses=errors(*AUTHENTICATED))
async def list_problems(
    query: Annotated[ProblemQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep, cipher: CipherDep
) -> ProblemListResponse:
    service = ProblemService(db, settings, cipher)
    solved, attempted = await service.user_progress(auth.user_id)
    problems, total, is_exact = await service.list_problems(query, is_reviewer=can_review(auth), solved_ids=solved)
    return ProblemListResponse(
        message="Problems retrieved successfully.",
        problems=[problem_list_item(problem, solved=solved, attempted=attempted) for problem in problems],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get("/{problem_id}", response_model=ProblemResponse, summary="Get a problem to solve", responses=errors(401, 404, 429))
async def get_problem(problem_id: ProblemIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> ProblemResponse:
    service = ProblemService(db, settings, cipher)
    problem = await service.get_visible(problem_id, is_reviewer=can_review(auth))
    solved, attempted = await service.user_progress(auth.user_id, [problem.public_id])
    enabled = await LanguageService(db).list_languages()
    return ProblemResponse(
        message="Problem retrieved successfully.",
        problem=problem_out(problem, TestCaseService(db, settings, cipher), enabled, solved=solved, attempted=attempted),
    )


@router.get(
    "/{problem_id}/author",
    response_model=ProblemAuthorResponse,
    summary="Get a problem as its author sees it",
    responses=errors(401, 403, 404, 429),
)
async def get_problem_for_author(
    problem_id: ProblemIdParam, auth: RequireReviewer, db: DbSession, settings: SettingsDep, cipher: CipherDep
) -> ProblemAuthorResponse:
    problem = await ProblemService(db, settings, cipher).get(problem_id)
    enabled = await LanguageService(db).list_languages()
    return ProblemAuthorResponse(
        message="Problem retrieved successfully.",
        problem=problem_author_out(problem, TestCaseService(db, settings, cipher), enabled, solved=set(), attempted=set()),
    )


@router.post(
    "",
    response_model=ProblemAuthorResponse,
    status_code=201,
    summary="Create a draft problem",
    responses=errors(401, 403, 422, 429),
    dependencies=[AuthoringRateLimit],
)
async def create_problem(data: ProblemCreate, auth: RequireAuthor, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> ProblemAuthorResponse:
    problem = await ProblemService(db, settings, cipher).create(auth.user_id, data)
    enabled = await LanguageService(db).list_languages()
    return ProblemAuthorResponse(
        message="Problem created successfully.",
        problem=problem_author_out(problem, TestCaseService(db, settings, cipher), enabled, solved=set(), attempted=set()),
    )


@router.patch(
    "/{problem_id}",
    response_model=ProblemAuthorResponse,
    summary="Edit a draft problem",
    responses=errors(400, 401, 403, 404, 422, 429),
    dependencies=[AuthoringRateLimit],
)
async def update_problem(
    problem_id: ProblemIdParam, data: ProblemUpdate, auth: RequireAuthor, db: DbSession, settings: SettingsDep, cipher: CipherDep
) -> ProblemAuthorResponse:
    service = ProblemService(db, settings, cipher)
    problem = await service.update(await service.get(problem_id), data)
    enabled = await LanguageService(db).list_languages()
    return ProblemAuthorResponse(
        message="Problem updated successfully.",
        problem=problem_author_out(problem, TestCaseService(db, settings, cipher), enabled, solved=set(), attempted=set()),
    )


@router.post(
    "/{problem_id}/publish",
    response_model=ProblemAuthorResponse,
    summary="Publish a draft: students can submit, and the problem is frozen",
    responses=errors(400, 401, 403, 404, 422, 429),
    dependencies=[AuthoringRateLimit],
)
async def publish_problem(problem_id: ProblemIdParam, auth: RequireAuthor, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> ProblemAuthorResponse:
    service = ProblemService(db, settings, cipher)
    problem = await service.publish(await service.get(problem_id))
    enabled = await LanguageService(db).list_languages()
    return ProblemAuthorResponse(
        message="Problem published successfully.",
        problem=problem_author_out(problem, TestCaseService(db, settings, cipher), enabled, solved=set(), attempted=set()),
    )


@router.post(
    "/{problem_id}/retire",
    response_model=ProblemAuthorResponse,
    summary="Retire a published problem: no new submissions, old results stay",
    responses=errors(400, 401, 403, 404, 429),
    dependencies=[AuthoringRateLimit],
)
async def retire_problem(problem_id: ProblemIdParam, auth: RequireAuthor, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> ProblemAuthorResponse:
    service = ProblemService(db, settings, cipher)
    problem = await service.retire(await service.get(problem_id))
    enabled = await LanguageService(db).list_languages()
    return ProblemAuthorResponse(
        message="Problem retired successfully.",
        problem=problem_author_out(problem, TestCaseService(db, settings, cipher), enabled, solved=set(), attempted=set()),
    )


@router.delete(
    "/{problem_id}",
    status_code=204,
    summary="Delete a draft problem",
    responses=errors(400, 401, 403, 404, 429),
    dependencies=[AuthoringRateLimit],
)
async def delete_problem(problem_id: ProblemIdParam, auth: RequireAuthor, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> None:
    service = ProblemService(db, settings, cipher)
    await service.delete(await service.get(problem_id))


@router.get("/{problem_id}/stats", response_model=ProblemStatsResponse, summary="Submission statistics for a problem", responses=errors(401, 403, 404, 429))
async def problem_stats(problem_id: ProblemIdParam, auth: RequireReviewer, db: DbSession, settings: SettingsDep, cipher: CipherDep) -> ProblemStatsResponse:
    service = ProblemService(db, settings, cipher)
    stats = await service.stats(await service.get(problem_id))
    return ProblemStatsResponse(message="Statistics retrieved successfully.", stats=ProblemStatsOut(**stats))
