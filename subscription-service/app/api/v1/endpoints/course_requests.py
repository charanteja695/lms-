from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder

from app.api.deps import (
    CourseRequestIdParam,
    CurrentAuth,
    DbSession,
    RedisDep,
    RequireAccountsManage,
    RequireInstitutionHead,
    SettingsDep,
    ensure_organization_visible,
    institutions_listed,
)
from app.api.responses import errors
from app.schemas.common import ListQuery
from app.schemas.course_request import (
    ApproveRequest,
    CourseRequestCreate,
    CourseRequestListResponse,
    CourseRequestOut,
    CourseRequestResponse,
    RejectRequest,
)
from app.schemas.subscription import SubscriptionOut, SubscriptionResponse
from app.services.course_request_service import CourseRequestService

router = APIRouter(prefix="/course-requests", tags=["Course requests"])


@router.post(
    "",
    response_model=CourseRequestResponse,
    status_code=201,
    summary="Request seats on a course",
    description="For the institution head's own institution. Requires the institution_head role.",
    responses=errors(400, 401, 403, 404, 409, 422),
)
async def submit_course_request(
    data: CourseRequestCreate, auth: RequireInstitutionHead, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> CourseRequestResponse:
    # require_institution_head already guarantees organization_id is set.
    assert auth.organization_id is not None
    request = await CourseRequestService(db, settings, redis).submit(auth.user_id, auth.organization_id, data)
    return CourseRequestResponse(
        message="Course request submitted successfully.", course_request=CourseRequestOut.model_validate(request)
    )


@router.get(
    "",
    response_model=CourseRequestListResponse,
    summary="List course requests",
    description="An institution head sees only their own institution's requests; accounts.manage sees all.",
    responses=errors(401, 422),
)
async def list_course_requests(
    query: Annotated[ListQuery, Query()], auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> CourseRequestListResponse:
    organization_ids = institutions_listed(auth)
    requests, total, is_exact = await CourseRequestService(db, settings, redis).list_requests(
        query, organization_ids=organization_ids
    )
    return CourseRequestListResponse(
        message="Course requests retrieved successfully.",
        course_requests=[CourseRequestOut.model_validate(request) for request in requests],
        page_context=PageContext.build(
            page=query.page, per_page=query.per_page, total=total, is_exact=is_exact,
            sort_column="created_time", sort_order=SortOrder(query.sort_order),
        ),
    )


@router.get(
    "/{course_request_id}",
    response_model=CourseRequestResponse,
    summary="Get a course request",
    responses=errors(401, 403, 404),
)
async def get_course_request(
    course_request_id: CourseRequestIdParam, auth: CurrentAuth, db: DbSession, settings: SettingsDep, redis: RedisDep
) -> CourseRequestResponse:
    request = await CourseRequestService(db, settings, redis).get(course_request_id)
    ensure_organization_visible(auth, request.organization_id)
    return CourseRequestResponse(
        message="Course request retrieved successfully.", course_request=CourseRequestOut.model_validate(request)
    )


@router.post(
    "/{course_request_id}/approve",
    response_model=SubscriptionResponse,
    summary="Approve a course request",
    description="Creates the subscription. Requires accounts.manage.",
    responses=errors(400, 401, 403, 404, 409, 422),
)
async def approve_course_request(
    course_request_id: CourseRequestIdParam,
    data: ApproveRequest,
    auth: RequireAccountsManage,
    db: DbSession,
    settings: SettingsDep,
    redis: RedisDep,
) -> SubscriptionResponse:
    service = CourseRequestService(db, settings, redis)
    request = await service.get(course_request_id)
    ensure_organization_visible(auth, request.organization_id)
    subscription = await service.approve(auth.user_id, request, data)
    return SubscriptionResponse(
        message="Course request approved; subscription activated.", subscription=SubscriptionOut.model_validate(subscription)
    )


@router.post(
    "/{course_request_id}/reject",
    response_model=CourseRequestResponse,
    summary="Reject a course request",
    responses=errors(400, 401, 403, 404, 422),
)
async def reject_course_request(
    course_request_id: CourseRequestIdParam,
    data: RejectRequest,
    auth: RequireAccountsManage,
    db: DbSession,
    settings: SettingsDep,
    redis: RedisDep,
) -> CourseRequestResponse:
    service = CourseRequestService(db, settings, redis)
    request = await service.get(course_request_id)
    ensure_organization_visible(auth, request.organization_id)
    request = await service.reject(auth.user_id, request, data.reason)
    return CourseRequestResponse(message="Course request rejected.", course_request=CourseRequestOut.model_validate(request))
