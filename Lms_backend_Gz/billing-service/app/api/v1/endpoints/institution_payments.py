"""Endpoints for Institution-managed student payment requests, Institution Head bulk/single payments, and Admin allocation reports."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder, SuccessResponse
from sqlalchemy import func, select

from app.api.deps import (
    DbSession,
    RequestIdParam,
    RequireBillingAdmin,
    RequireIndependentStudent,
    RequireInstitutionHead,
    RequireStudentUser,
    SettingsDep,
    TxIdParam,
    WriteRateLimit,
)
from app.api.responses import AUTHENTICATED, errors
from app.api.v1.endpoints.student_subscriptions import _plan_out, _plan_public_id_map, _tx_out
from app.models.student_subscription import StudentPaymentAllocation, StudentPaymentRequest
from app.schemas.student_subscription import (
    AllocationListResponse,
    AssignStudentCourseIn,
    CreatePaymentRequestIn,
    DecisionNoteIn,
    GatewayCheckoutPayload,
    InstitutionAllocationPreviewOut,
    InstitutionCheckoutCreateIn,
    InstitutionCheckoutPreviewIn,
    InstitutionCheckoutPreviewResponse,
    InstitutionCheckoutSessionResponse,
    InstitutionCheckoutSummaryOut,
    InstitutionStudentItem,
    InstitutionStudentListResponse,
    InstitutionTransactionDetailResponse,
    StudentAccountContextResponse,
    StudentPaymentAllocationOut,
    StudentPaymentRequestListResponse,
    StudentPaymentRequestOut,
    StudentPaymentRequestResponse,
    TestGatewayCallbackRequest,
    TransactionListResponse,
    VerifyStudentPaymentRequest,
)
from app.services.institution_payment_service import InstitutionPaymentService

student_requests_router = APIRouter(prefix="/student", tags=["Student Payment Requests"])
institution_payments_router = APIRouter(prefix="/institution/payments", tags=["Institution Student Payments"])
admin_requests_router = APIRouter(prefix="/admin", tags=["Admin Student Payment Reports"])


def _req_out(r: StudentPaymentRequest, plan_public_id: str | None = None) -> StudentPaymentRequestOut:
    return StudentPaymentRequestOut(
        public_id=r.public_id,
        request_ref=r.request_ref,
        student_user_id=r.student_user_id,
        student_name=r.student_name,
        student_email=r.student_email,
        organization_id=r.organization_id,
        course_id=r.course_id,
        course_title=r.course_title,
        plan_id=plan_public_id or str(r.plan_id),
        plan_code=r.plan_code,
        plan_name=r.plan_name,
        amount_paise=r.amount_paise,
        status=r.status,
        student_note=r.student_note,
        decision_note=r.decision_note,
        reviewed_by_user_id=r.reviewed_by_user_id,
        reviewed_at=r.reviewed_at,
        paid_by_user_id=r.paid_by_user_id,
        paid_at=r.paid_at,
        transaction_id=str(r.transaction_id) if r.transaction_id else None,
        created_at=r.created_at,
    )


def _alloc_out(a: StudentPaymentAllocation, plan_public_id: str | None = None) -> StudentPaymentAllocationOut:
    return StudentPaymentAllocationOut(
        public_id=a.public_id,
        transaction_id=str(a.transaction_id),
        organization_id=a.organization_id,
        payer_user_id=a.payer_user_id,
        student_user_id=a.student_user_id,
        student_name=a.student_name,
        student_email=a.student_email,
        course_id=a.course_id,
        course_title=a.course_title,
        plan_id=plan_public_id or str(a.plan_id),
        plan_code=a.plan_code,
        plan_name=a.plan_name,
        original_amount_paise=a.original_amount_paise,
        discount_paise=a.discount_paise,
        tax_paise=a.tax_paise,
        allocated_amount_paise=a.allocated_amount_paise,
        status=a.status,
        activated_at=a.activated_at,
        created_at=a.created_at,
    )


# ------------------------------------------------------------------ Student: Category & Payment Requests
@student_requests_router.get(
    "/account-context",
    response_model=StudentAccountContextResponse,
    summary="Resolve whether student is institution-managed or independent",
    responses=errors(*AUTHENTICATED),
)
async def student_account_context(auth: RequireStudentUser, db: DbSession, settings: SettingsDep) -> StudentAccountContextResponse:
    ctx = await InstitutionPaymentService(db, settings).get_student_account_context(auth)
    return StudentAccountContextResponse(message="", **ctx)


@student_requests_router.post(
    "/payment-requests",
    response_model=StudentPaymentRequestResponse,
    status_code=201,
    summary="Submit a payment request to Institution Head (institution students only)",
    responses=errors(*AUTHENTICATED, 400, 403, 404, 409),
    dependencies=[WriteRateLimit],
)
async def create_student_payment_request(
    body: CreatePaymentRequestIn,
    auth: RequireStudentUser,
    db: DbSession,
    settings: SettingsDep,
) -> StudentPaymentRequestResponse:
    from app.core.exceptions import PermissionDeniedError
    if auth.organization_id is not None:
        raise PermissionDeniedError(
            "Institution students receive course access directly through their institution. Individual payment requests are disabled.",
            code="PAYMENT_REQUESTS_DISABLED",
        )
    req = await InstitutionPaymentService(db, settings).create_payment_request(
        auth,
        course_id=int(body.course_id),
        plan_public_id=str(body.plan_id),
        student_note=body.student_note,
    )
    pmap = await _plan_public_id_map(db)
    return StudentPaymentRequestResponse(message="Payment request sent to your Institution Head.", payment_request=_req_out(req, pmap.get(req.plan_id)))


@student_requests_router.get(
    "/payment-requests",
    response_model=StudentPaymentRequestListResponse,
    summary="List my payment requests",
    responses=errors(*AUTHENTICATED),
)
async def list_student_payment_requests(
    auth: RequireIndependentStudent,
    db: DbSession,
    settings: SettingsDep,
    status: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StudentPaymentRequestListResponse:
    rows, total = await InstitutionPaymentService(db, settings).list_student_payment_requests(auth, status=status, page=page, per_page=per_page)
    pmap = await _plan_public_id_map(db)
    return StudentPaymentRequestListResponse(
        message="",
        requests=[_req_out(r, pmap.get(r.plan_id)) for r in rows],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


@student_requests_router.post(
    "/payment-requests/{request_id}/cancel",
    response_model=StudentPaymentRequestResponse,
    summary="Cancel a pending payment request",
    responses=errors(*AUTHENTICATED, 403, 404, 409),
    dependencies=[WriteRateLimit],
)
async def cancel_student_payment_request(
    request_id: RequestIdParam,
    auth: RequireIndependentStudent,
    db: DbSession,
    settings: SettingsDep,
) -> StudentPaymentRequestResponse:
    req = await InstitutionPaymentService(db, settings).cancel_payment_request(auth, request_id)
    pmap = await _plan_public_id_map(db)
    return StudentPaymentRequestResponse(message="Payment request cancelled.", payment_request=_req_out(req, pmap.get(req.plan_id)))


# ------------------------------------------------------------------ Institution Head: Students, Requests & Bulk/Single Checkout
@institution_payments_router.get(
    "/students",
    response_model=InstitutionStudentListResponse,
    summary="List students in my institution with course & payment statuses",
    responses=errors(*AUTHENTICATED, 403),
)
async def institution_list_students(
    auth: RequireInstitutionHead,
    db: DbSession,
    settings: SettingsDep,
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> InstitutionStudentListResponse:
    res = await InstitutionPaymentService(db, settings).list_institution_students(auth, search=search, page=page, per_page=per_page)
    return InstitutionStudentListResponse(
        message="",
        students=[InstitutionStudentItem(**s) for s in res["students"]],
        approved_courses=res["approved_courses"],
        page_context=PageContext.build(page=page, per_page=per_page, total=res["total"], is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


@institution_payments_router.post(
    "/students/assign-course",
    response_model=StudentPaymentRequestResponse,
    summary="Assign an approved course & plan to a student (pending payment)",
    responses=errors(*AUTHENTICATED, 400, 403, 404),
    dependencies=[WriteRateLimit],
)
async def institution_assign_student_course(
    body: AssignStudentCourseIn,
    auth: RequireInstitutionHead,
    db: DbSession,
    settings: SettingsDep,
) -> StudentPaymentRequestResponse:
    req = await InstitutionPaymentService(db, settings).assign_student_course(
        auth,
        student_user_id=int(body.student_user_id),
        course_id=int(body.course_id),
        plan_public_id=str(body.plan_id) if body.plan_id else None,
    )
    pmap = await _plan_public_id_map(db)
    return StudentPaymentRequestResponse(message="Course assigned to student (ready for payment).", payment_request=_req_out(req, pmap.get(req.plan_id)))


@institution_payments_router.get(
    "/requests",
    response_model=StudentPaymentRequestListResponse,
    summary="List student payment requests for my institution",
    responses=errors(*AUTHENTICATED, 403),
)
async def institution_list_requests(
    auth: RequireInstitutionHead,
    db: DbSession,
    settings: SettingsDep,
    status: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StudentPaymentRequestListResponse:
    rows, total = await InstitutionPaymentService(db, settings).list_institution_requests(
        auth, status=status, search=search, page=page, per_page=per_page
    )
    pmap = await _plan_public_id_map(db)
    return StudentPaymentRequestListResponse(
        message="",
        requests=[_req_out(r, pmap.get(r.plan_id)) for r in rows],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


@institution_payments_router.post(
    "/requests/{request_id}/approve",
    response_model=StudentPaymentRequestResponse,
    summary="Approve a student payment request",
    responses=errors(*AUTHENTICATED, 403, 404, 409),
    dependencies=[WriteRateLimit],
)
async def institution_approve_request(
    request_id: RequestIdParam,
    body: DecisionNoteIn,
    auth: RequireInstitutionHead,
    db: DbSession,
    settings: SettingsDep,
) -> StudentPaymentRequestResponse:
    req = await InstitutionPaymentService(db, settings).approve_request(auth, request_id, body.decision_note)
    pmap = await _plan_public_id_map(db)
    return StudentPaymentRequestResponse(message="Payment request approved.", payment_request=_req_out(req, pmap.get(req.plan_id)))


@institution_payments_router.post(
    "/requests/{request_id}/reject",
    response_model=StudentPaymentRequestResponse,
    summary="Reject a student payment request",
    responses=errors(*AUTHENTICATED, 403, 404, 409),
    dependencies=[WriteRateLimit],
)
async def institution_reject_request(
    request_id: RequestIdParam,
    body: DecisionNoteIn,
    auth: RequireInstitutionHead,
    db: DbSession,
    settings: SettingsDep,
) -> StudentPaymentRequestResponse:
    req = await InstitutionPaymentService(db, settings).reject_request(auth, request_id, body.decision_note)
    pmap = await _plan_public_id_map(db)
    return StudentPaymentRequestResponse(message="Payment request rejected.", payment_request=_req_out(req, pmap.get(req.plan_id)))


@institution_payments_router.post(
    "/checkout/preview",
    response_model=InstitutionCheckoutPreviewResponse,
    summary="Preview single or bulk student payment summary for Institution Head",
    responses=errors(*AUTHENTICATED, 400, 403, 404, 409),
)
async def institution_checkout_preview(
    body: InstitutionCheckoutPreviewIn,
    auth: RequireInstitutionHead,
    db: DbSession,
    settings: SettingsDep,
) -> InstitutionCheckoutPreviewResponse:
    s = await InstitutionPaymentService(db, settings).preview_institution_checkout(
        auth,
        student_ids=[int(x) for x in body.student_ids],
        plan_public_id=str(body.plan_id),
        course_id=int(body.course_id) if body.course_id is not None else None,
        request_ids=[str(r) for r in body.request_ids],
    )
    return InstitutionCheckoutPreviewResponse(
        message="",
        summary=InstitutionCheckoutSummaryOut(
            plan=_plan_out(s["plan"]),
            student_count=s["student_count"],
            currency=s["currency"],
            original_total_paise=s["original_total_paise"],
            discount_total_paise=s["discount_total_paise"],
            tax_rate_percent=s["tax_rate_percent"],
            tax_total_paise=s["tax_total_paise"],
            grand_total_paise=s["grand_total_paise"],
            allocations=[
                InstitutionAllocationPreviewOut(**{k: v for k, v in a.items() if k != "_req_obj"})
                for a in s["allocations"]
            ],
            accepted_methods=s["accepted_methods"],
            payments_enabled=s["payments_enabled"],
        ),
    )


@institution_payments_router.post(
    "/checkout",
    response_model=InstitutionCheckoutSessionResponse,
    status_code=201,
    summary="Create single or bulk payment order on behalf of selected students",
    responses=errors(*AUTHENTICATED, 400, 403, 404, 409),
    dependencies=[WriteRateLimit],
)
async def institution_checkout_create(
    body: InstitutionCheckoutCreateIn,
    auth: RequireInstitutionHead,
    db: DbSession,
    settings: SettingsDep,
) -> InstitutionCheckoutSessionResponse:
    tx, allocs, gw = await InstitutionPaymentService(db, settings).create_institution_checkout(
        auth,
        student_ids=[int(x) for x in body.student_ids],
        plan_public_id=str(body.plan_id),
        payment_method=body.payment_method,
        course_id=int(body.course_id) if body.course_id is not None else None,
        request_ids=[str(r) for r in body.request_ids],
    )
    pmap = await _plan_public_id_map(db)
    return InstitutionCheckoutSessionResponse(
        message="Institution payment order created.",
        transaction=_tx_out(tx, pmap.get(tx.plan_id)),
        allocations=[_alloc_out(a, pmap.get(a.plan_id)) for a in allocs],
        gateway=GatewayCheckoutPayload(**gw),
    )


@institution_payments_router.post(
    "/transactions/{tx_id}/verify",
    response_model=InstitutionTransactionDetailResponse,
    summary="Verify institution payment signature & activate allocated student subscriptions",
    responses=errors(*AUTHENTICATED, 400, 403, 404),
    dependencies=[WriteRateLimit],
)
async def institution_verify_payment(
    tx_id: TxIdParam,
    body: VerifyStudentPaymentRequest,
    auth: RequireInstitutionHead,
    db: DbSession,
    settings: SettingsDep,
) -> InstitutionTransactionDetailResponse:
    tx, allocs = await InstitutionPaymentService(db, settings).verify_institution_payment(
        auth,
        tx_id,
        razorpay_order_id=body.razorpay_order_id,
        razorpay_payment_id=body.razorpay_payment_id,
        razorpay_signature=body.razorpay_signature,
        outcome=body.outcome,
        failure_reason=body.failure_reason,
    )
    pmap = await _plan_public_id_map(db)
    return InstitutionTransactionDetailResponse(
        message="Payment verified and student access activated." if tx.status == "succeeded" else "Payment status updated.",
        transaction=_tx_out(tx, pmap.get(tx.plan_id)),
        allocations=[_alloc_out(a, pmap.get(a.plan_id)) for a in allocs],
    )


@institution_payments_router.post(
    "/transactions/{tx_id}/test-callback",
    response_model=InstitutionTransactionDetailResponse,
    summary="Simulate gateway callback for institution checkout in test mode",
    responses=errors(*AUTHENTICATED, 403, 404),
    dependencies=[WriteRateLimit],
)
async def institution_test_callback(
    tx_id: TxIdParam,
    body: TestGatewayCallbackRequest,
    auth: RequireInstitutionHead,
    db: DbSession,
    settings: SettingsDep,
) -> InstitutionTransactionDetailResponse:
    tx, allocs = await InstitutionPaymentService(db, settings).test_callback_institution_payment(
        auth,
        tx_id,
        outcome=body.outcome,
        payment_id=body.payment_id,
        failure_reason=body.failure_reason,
    )
    pmap = await _plan_public_id_map(db)
    return InstitutionTransactionDetailResponse(
        message="Test payment callback processed.",
        transaction=_tx_out(tx, pmap.get(tx.plan_id)),
        allocations=[_alloc_out(a, pmap.get(a.plan_id)) for a in allocs],
    )


@institution_payments_router.get(
    "/transactions",
    response_model=TransactionListResponse,
    summary="List all payment transactions for my institution",
    responses=errors(*AUTHENTICATED, 403),
)
async def institution_list_transactions(
    auth: RequireInstitutionHead,
    db: DbSession,
    settings: SettingsDep,
    status: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TransactionListResponse:
    rows, total = await InstitutionPaymentService(db, settings).list_institution_transactions(auth, status=status, page=page, per_page=per_page)
    pmap = await _plan_public_id_map(db)
    return TransactionListResponse(
        message="",
        transactions=[_tx_out(r, pmap.get(r.plan_id)) for r in rows],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


@institution_payments_router.get(
    "/transactions/{tx_id}",
    response_model=InstitutionTransactionDetailResponse,
    summary="Get institution transaction and student-level allocations",
    responses=errors(*AUTHENTICATED, 403, 404),
)
async def institution_get_transaction(
    tx_id: TxIdParam,
    auth: RequireInstitutionHead,
    db: DbSession,
    settings: SettingsDep,
) -> InstitutionTransactionDetailResponse:
    tx, allocs = await InstitutionPaymentService(db, settings).get_institution_transaction_detail(auth, tx_id)
    pmap = await _plan_public_id_map(db)
    return InstitutionTransactionDetailResponse(
        message="",
        transaction=_tx_out(tx, pmap.get(tx.plan_id)),
        allocations=[_alloc_out(a, pmap.get(a.plan_id)) for a in allocs],
    )


@institution_payments_router.get(
    "/allocations",
    response_model=AllocationListResponse,
    summary="List student-level payment allocations in my institution",
    responses=errors(*AUTHENTICATED, 403),
)
async def institution_list_allocations(
    auth: RequireInstitutionHead,
    db: DbSession,
    settings: SettingsDep,
    student_user_id: Annotated[int | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AllocationListResponse:
    rows, total = await InstitutionPaymentService(db, settings).list_institution_allocations(
        auth, student_user_id=student_user_id, page=page, per_page=per_page
    )
    pmap = await _plan_public_id_map(db)
    return AllocationListResponse(
        message="",
        allocations=[_alloc_out(a, pmap.get(a.plan_id)) for a in rows],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


# ------------------------------------------------------------------ Admin: Payment Requests & Student Allocations
@admin_requests_router.get(
    "/payment-requests",
    response_model=StudentPaymentRequestListResponse,
    summary="List all student payment requests across institutions (admin)",
    responses=errors(*AUTHENTICATED, 403),
)
async def admin_list_payment_requests(
    auth: RequireBillingAdmin,
    db: DbSession,
    status: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> StudentPaymentRequestListResponse:
    stmt = select(StudentPaymentRequest)
    count_stmt = select(func.count()).select_from(StudentPaymentRequest)
    if status:
        stmt = stmt.where(StudentPaymentRequest.status == status)
        count_stmt = count_stmt.where(StudentPaymentRequest.status == status)
    total = int((await db.execute(count_stmt)).scalar_one())
    rows = (
        await db.execute(stmt.order_by(StudentPaymentRequest.created_at.desc()).offset((page - 1) * per_page).limit(per_page))
    ).scalars().all()
    pmap = await _plan_public_id_map(db)
    return StudentPaymentRequestListResponse(
        message="",
        requests=[_req_out(r, pmap.get(r.plan_id)) for r in rows],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


@admin_requests_router.get(
    "/allocations",
    response_model=AllocationListResponse,
    summary="List all student-level payment allocations (admin)",
    responses=errors(*AUTHENTICATED, 403),
)
async def admin_list_allocations(
    auth: RequireBillingAdmin,
    db: DbSession,
    organization_id: Annotated[int | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AllocationListResponse:
    stmt = select(StudentPaymentAllocation)
    count_stmt = select(func.count()).select_from(StudentPaymentAllocation)
    if organization_id is not None:
        stmt = stmt.where(StudentPaymentAllocation.organization_id == organization_id)
        count_stmt = count_stmt.where(StudentPaymentAllocation.organization_id == organization_id)
    total = int((await db.execute(count_stmt)).scalar_one())
    rows = (
        await db.execute(stmt.order_by(StudentPaymentAllocation.created_at.desc()).offset((page - 1) * per_page).limit(per_page))
    ).scalars().all()
    pmap = await _plan_public_id_map(db)
    return AllocationListResponse(
        message="",
        allocations=[_alloc_out(a, pmap.get(a.plan_id)) for a in rows],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )
