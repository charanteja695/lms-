from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import DbSession, RequireReviewer, SettingsDep, SubmissionIdParam
from app.api.responses import errors
from app.schemas.common import ReviewSubmissionQuery
from app.schemas.submission import (
    ReviewSubmissionListItem,
    ReviewSubmissionListResponse,
    ReviewSubmissionOut,
    ReviewSubmissionResponse,
    SimilarMatchesResponse,
    SimilarMatchOut,
)
from app.services.similarity_service import SimilarityService
from app.services.submission_service import SubmissionService

router = APIRouter(prefix="/review", tags=["Review"])


@router.get(
    "/submissions",
    response_model=ReviewSubmissionListResponse,
    summary="List everyone's submissions, with the plagiarism signal",
    description="Filter with `flagged=true` for submissions that look like copies of another student's.",
    responses=errors(401, 403, 422, 429),
)
async def list_submissions(
    query: Annotated[ReviewSubmissionQuery, Query()], auth: RequireReviewer, db: DbSession, settings: SettingsDep
) -> ReviewSubmissionListResponse:
    submissions, total, is_exact = await SubmissionService(db, settings).list_submissions(query, user_id=None)
    return ReviewSubmissionListResponse(
        message="Submissions retrieved successfully.",
        submissions=[ReviewSubmissionListItem.model_validate(submission) for submission in submissions],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get("/submissions/{submission_id}", response_model=ReviewSubmissionResponse, summary="Get any submission", responses=errors(401, 403, 404, 429))
async def get_submission(submission_id: SubmissionIdParam, auth: RequireReviewer, db: DbSession, settings: SettingsDep) -> ReviewSubmissionResponse:
    submission = await SubmissionService(db, settings).get(submission_id)
    return ReviewSubmissionResponse(message="Submission retrieved successfully.", submission=ReviewSubmissionOut.model_validate(submission))


@router.get(
    "/submissions/{submission_id}/similar",
    response_model=SimilarMatchesResponse,
    summary="The closest other submissions to this one",
    description="A similarity signal for a human to review: never proof of copying. Compared within the same problem, "
    "across different people.",
    responses=errors(401, 403, 404, 429),
)
async def similar_submissions(submission_id: SubmissionIdParam, auth: RequireReviewer, db: DbSession, settings: SettingsDep) -> SimilarMatchesResponse:
    submission = await SubmissionService(db, settings).get(submission_id)
    matches = await SimilarityService(db, settings).similar_to(submission)
    return SimilarMatchesResponse(
        message="Similar submissions retrieved successfully.",
        matches=[
            SimilarMatchOut(
                submission_id=other.public_id,
                user_id=other.user_id,
                similarity_percent=percent,
                verdict=other.verdict,
                created_at=other.created_at,
            )
            for other, percent in matches
        ],
    )
