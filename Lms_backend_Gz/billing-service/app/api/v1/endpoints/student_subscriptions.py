"""Admin plan management, payment settings, student checkout, verification, UPI QR, subscriptions, and payment history."""

from datetime import UTC, datetime, time
from typing import Annotated

from fastapi import APIRouter, Query
from lms_common.envelopes import PageContext, SortOrder, SuccessResponse
from sqlalchemy import select

from app.api.deps import (
    DbSession,
    PaymentGatewayDep,
    PlanIdParam,
    RequireBillingAdmin,
    RequireIndependentStudent,
    RequireStudentUser,
    SettingsDep,
    TxIdParam,
    WriteRateLimit,
)
from app.api.responses import AUTHENTICATED, errors
from app.models.student_subscription import (
    PaymentSettings,
    StudentPaymentTransaction,
    StudentSubscription,
    StudentSubscriptionCourse,
    SubscriptionPlan,
)
from app.schemas.student_subscription import (
    AdminPaymentReportsResponse,
    CheckoutPreviewRequest,
    CheckoutPreviewResponse,
    CheckoutSummaryOut,
    EnrollCourseUnderPlanRequest,
    GatewayCheckoutPayload,
    PaymentSettingsIn,
    PaymentSettingsOut,
    PaymentSettingsResponse,
    ReceiptResponse,
    StudentCheckoutRequest,
    StudentCheckoutResponse,
    StudentPaymentTransactionOut,
    StudentSubscriptionOut,
    StudentSubscriptionOverviewResponse,
    SubscriptionCourseOut,
    SubscriptionPlanCreate,
    SubscriptionPlanListResponse,
    SubscriptionPlanOut,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdate,
    TestGatewayCallbackRequest,
    TransactionListResponse,
    VerifyPaymentResponse,
    VerifyStudentPaymentRequest,
)
from app.services.student_subscription_service import StudentSubscriptionService

admin_plans_router = APIRouter(prefix="/admin/subscription-plans", tags=["Student Plans (admin)"])
admin_settings_router = APIRouter(prefix="/admin/payment-settings", tags=["Payment Settings (admin)"])
admin_tx_router = APIRouter(prefix="/admin/transactions", tags=["Transactions (admin)"])
admin_reports_router = APIRouter(prefix="/admin/payment-reports", tags=["Payment Reports (admin)"])
student_router = APIRouter(prefix="/student", tags=["Student Subscriptions & Payments"])


def _plan_out(plan: SubscriptionPlan) -> SubscriptionPlanOut:
    return SubscriptionPlanOut.model_validate(plan)


def _settings_out(row: PaymentSettings, service: StudentSubscriptionService) -> PaymentSettingsOut:
    return PaymentSettingsOut(
        payments_enabled=row.payments_enabled,
        min_amount_paise=row.min_amount_paise,
        max_amount_paise=row.max_amount_paise,
        accepted_methods=dict(row.accepted_methods or {}),
        tax_rate_percent=row.tax_rate_percent,
        upgrade_pricing_mode=row.upgrade_pricing_mode,
        upi_vpa=row.upi_vpa,
        upi_merchant_name=row.upi_merchant_name,
        gateway_provider=service.settings.PAYMENT_PROVIDER,
        test_mode=service.is_test_mode,
        updated_at=row.updated_at,
    )


def _sub_out(
    sub: StudentSubscription,
    courses: list[StudentSubscriptionCourse],
    plan_public_id: str | None = None,
) -> StudentSubscriptionOut:
    return StudentSubscriptionOut(
        public_id=sub.public_id,
        plan_id=plan_public_id or str(sub.plan_id),
        plan_code=sub.plan_code,
        plan_name=sub.plan_name,
        price_paise=sub.price_paise,
        duration_days=sub.duration_days,
        max_courses=sub.max_courses,
        features=list(sub.features_snapshot or []),
        assessment_access=dict(sub.assessment_access_snapshot or {}),
        certificate_level=sub.certificate_level,
        status=sub.status.value if hasattr(sub.status, "value") else str(sub.status),
        starts_at=sub.starts_at,
        ends_at=sub.ends_at,
        created_at=sub.created_at,
        courses=[
            SubscriptionCourseOut(
                course_id=c.course_id,
                course_title=c.course_title,
                granted_at=c.granted_at,
            )
            for c in courses
        ],
    )


def _tx_out(tx: StudentPaymentTransaction, plan_public_id: str | None = None) -> StudentPaymentTransactionOut:
    return StudentPaymentTransactionOut(
        public_id=tx.public_id,
        transaction_ref=tx.transaction_ref,
        user_id=tx.user_id,
        payer_user_id=tx.payer_user_id or tx.user_id,
        payer_role=tx.payer_role or "student",
        payment_scope=tx.payment_scope or "independent_student",
        student_count=tx.student_count or 1,
        organization_id=tx.organization_id or 0,
        plan_id=plan_public_id or str(tx.plan_id),
        plan_code=tx.plan_code,
        plan_name=tx.plan_name,
        course_id=tx.course_id,
        course_title=tx.course_title,
        action_type=tx.action_type.value if hasattr(tx.action_type, "value") else str(tx.action_type),
        original_amount_paise=tx.original_amount_paise,
        discount_paise=tx.discount_paise,
        tax_paise=tx.tax_paise,
        total_amount_paise=tx.total_amount_paise,
        currency=tx.currency,
        payment_method=tx.payment_method,
        gateway_provider=tx.gateway_provider,
        gateway_order_id=tx.gateway_order_id,
        gateway_payment_id=tx.gateway_payment_id,
        upi_qr_payload=tx.upi_qr_payload,
        status=tx.status.value if hasattr(tx.status, "value") else str(tx.status),
        failure_reason=tx.failure_reason,
        invoice_number=tx.invoice_number,
        expires_at=tx.expires_at,
        paid_at=tx.paid_at,
        created_at=tx.created_at,
    )


async def _plan_public_id_map(db: DbSession) -> dict[object, str]:
    rows = (await db.execute(select(SubscriptionPlan.id, SubscriptionPlan.public_id))).all()
    return {row[0]: str(row[1]) for row in rows}


def _parse_date_bound(value: str | None, *, end_of_day: bool) -> datetime | None:
    if not value or not value.strip():
        return None
    raw = value.strip()
    if len(raw) == 10:
        d = datetime.strptime(raw, "%Y-%m-%d").date()
        return datetime.combine(d, time.max if end_of_day else time.min, tzinfo=UTC)
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


# ------------------------------------------------------------------ Admin: Subscription Plans
@admin_plans_router.get("", response_model=SubscriptionPlanListResponse, summary="List subscription plans (admin)", responses=errors(*AUTHENTICATED))
async def admin_list_plans(auth: RequireBillingAdmin, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> SubscriptionPlanListResponse:
    plans = await StudentSubscriptionService(db, settings, gateway).list_plans(active_only=False)
    return SubscriptionPlanListResponse(message="", plans=[_plan_out(p) for p in plans])


@admin_plans_router.post(
    "",
    response_model=SubscriptionPlanResponse,
    status_code=201,
    summary="Create subscription plan (admin)",
    responses=errors(*AUTHENTICATED, 400, 409),
    dependencies=[WriteRateLimit],
)
async def admin_create_plan(
    body: SubscriptionPlanCreate,
    auth: RequireBillingAdmin,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> SubscriptionPlanResponse:
    plan = await StudentSubscriptionService(db, settings, gateway).create_plan(body.model_dump())
    return SubscriptionPlanResponse(message="Subscription plan created.", plan=_plan_out(plan))


@admin_plans_router.patch(
    "/{plan_id}",
    response_model=SubscriptionPlanResponse,
    summary="Update subscription plan (admin)",
    responses=errors(*AUTHENTICATED, 400, 404),
    dependencies=[WriteRateLimit],
)
async def admin_update_plan(
    plan_id: PlanIdParam,
    body: SubscriptionPlanUpdate,
    auth: RequireBillingAdmin,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> SubscriptionPlanResponse:
    payload = body.model_dump(exclude_unset=True)
    plan = await StudentSubscriptionService(db, settings, gateway).update_plan(plan_id, payload)
    return SubscriptionPlanResponse(message="Subscription plan updated.", plan=_plan_out(plan))


@admin_plans_router.delete(
    "/{plan_id}",
    response_model=SuccessResponse,
    summary="Delete or archive subscription plan (admin)",
    responses=errors(*AUTHENTICATED, 404),
    dependencies=[WriteRateLimit],
)
async def admin_delete_plan(
    plan_id: PlanIdParam,
    auth: RequireBillingAdmin,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> SuccessResponse:
    await StudentSubscriptionService(db, settings, gateway).delete_plan(plan_id)
    return SuccessResponse(message="Subscription plan removed.")


# ------------------------------------------------------------------ Admin: Payment Settings & Reports
@admin_settings_router.get("", response_model=PaymentSettingsResponse, summary="Get payment settings (admin)", responses=errors(*AUTHENTICATED))
async def admin_get_payment_settings(
    auth: RequireBillingAdmin,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> PaymentSettingsResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    row = await service.get_payment_settings()
    return PaymentSettingsResponse(message="", settings=_settings_out(row, service))


@admin_settings_router.put(
    "",
    response_model=PaymentSettingsResponse,
    summary="Update payment settings (admin)",
    responses=errors(*AUTHENTICATED, 400),
    dependencies=[WriteRateLimit],
)
async def admin_update_payment_settings(
    body: PaymentSettingsIn,
    auth: RequireBillingAdmin,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> PaymentSettingsResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    row = await service.update_payment_settings(auth, body.model_dump())
    return PaymentSettingsResponse(message="Payment settings saved.", settings=_settings_out(row, service))


@admin_tx_router.get("", response_model=TransactionListResponse, summary="List all student payment transactions (admin)", responses=errors(*AUTHENTICATED))
async def admin_list_transactions(
    auth: RequireBillingAdmin,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
    status: Annotated[str | None, Query()] = None,
    from_date: Annotated[str | None, Query()] = None,
    to_date: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TransactionListResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    rows, total = await service.list_transactions(
        user_id=None,
        status=status,
        from_date=_parse_date_bound(from_date, end_of_day=False),
        to_date=_parse_date_bound(to_date, end_of_day=True),
        search=search,
        page=page,
        per_page=per_page,
    )
    pmap = await _plan_public_id_map(db)
    return TransactionListResponse(
        message="",
        transactions=[_tx_out(r, pmap.get(r.plan_id)) for r in rows],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


@admin_reports_router.get("", response_model=AdminPaymentReportsResponse, summary="Payment revenue & subscription metrics (admin)", responses=errors(*AUTHENTICATED))
async def admin_payment_reports(
    auth: RequireBillingAdmin,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> AdminPaymentReportsResponse:
    data = await StudentSubscriptionService(db, settings, gateway).admin_payment_reports()
    return AdminPaymentReportsResponse(message="", **data)


# ------------------------------------------------------------------ Student: Plans, Checkout, Verify, Subscription, History
@student_router.get("/plans", response_model=SubscriptionPlanListResponse, summary="List active subscription plans", responses=errors(*AUTHENTICATED))
async def student_list_plans(auth: RequireStudentUser, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> SubscriptionPlanListResponse:
    plans = await StudentSubscriptionService(db, settings, gateway).list_plans(active_only=True)
    return SubscriptionPlanListResponse(message="", plans=[_plan_out(p) for p in plans])


@student_router.get("/payment-settings", response_model=PaymentSettingsResponse, summary="Public payment configuration for students", responses=errors(*AUTHENTICATED))
async def student_payment_settings(auth: RequireStudentUser, db: DbSession, settings: SettingsDep, gateway: PaymentGatewayDep) -> PaymentSettingsResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    row = await service.get_payment_settings()
    return PaymentSettingsResponse(message="", settings=_settings_out(row, service))


@student_router.post(
    "/checkout/preview",
    response_model=CheckoutPreviewResponse,
    summary="Compute server-side checkout breakdown (discount, tax, total)",
    responses=errors(*AUTHENTICATED, 400, 403, 404, 409),
)
async def student_checkout_preview(
    body: CheckoutPreviewRequest,
    auth: RequireIndependentStudent,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> CheckoutPreviewResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    calc = await service.compute_checkout_summary(
        auth,
        plan_public_id=int(body.plan_id),
        course_id=int(body.course_id) if body.course_id is not None else None,
        action_type=body.action_type,
    )
    settings_row: PaymentSettings = calc["settings_row"]
    return CheckoutPreviewResponse(
        message="",
        summary=CheckoutSummaryOut(
            plan=_plan_out(calc["plan"]),
            course_id=str(calc["course_id"]) if calc["course_id"] is not None else None,
            course_title=calc["course_title"],
            action_type=calc["action_type"],
            original_amount_paise=calc["original_amount_paise"],
            discount_paise=calc["discount_paise"],
            discount_note=calc["discount_note"],
            taxable_paise=calc["taxable_paise"],
            tax_paise=calc["tax_paise"],
            tax_rate_percent=calc["tax_rate_percent"],
            total_amount_paise=calc["total_amount_paise"],
            currency="INR",
            accepted_methods=dict(settings_row.accepted_methods or {}),
            payments_enabled=settings_row.payments_enabled,
            current_plan_name=calc["current_plan_name"],
        ),
    )


@student_router.post(
    "/checkout",
    response_model=StudentCheckoutResponse,
    status_code=201,
    summary="Create payment order and pending transaction",
    responses=errors(*AUTHENTICATED, 400, 403, 404, 409, 503),
    dependencies=[WriteRateLimit],
)
async def student_checkout(
    body: StudentCheckoutRequest,
    auth: RequireIndependentStudent,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> StudentCheckoutResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    tx, checkout = await service.start_checkout(
        auth,
        plan_public_id=int(body.plan_id),
        course_id=int(body.course_id) if body.course_id is not None else None,
        payment_method=body.payment_method,
        action_type=body.action_type,
        student_name=body.student_name,
        student_email=body.student_email,
    )
    pmap = await _plan_public_id_map(db)
    return StudentCheckoutResponse(
        message="Order created. Complete payment to activate your subscription.",
        transaction=_tx_out(tx, pmap.get(tx.plan_id)),
        checkout=GatewayCheckoutPayload(**checkout),
    )


@student_router.post(
    "/payments/{tx_id}/verify",
    response_model=VerifyPaymentResponse,
    summary="Verify gateway signature and activate subscription",
    responses=errors(*AUTHENTICATED, 400, 404),
    dependencies=[WriteRateLimit],
)
async def student_verify_payment(
    tx_id: TxIdParam,
    body: VerifyStudentPaymentRequest,
    auth: RequireIndependentStudent,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> VerifyPaymentResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    tx, active = await service.verify_student_payment(
        auth,
        tx_id,
        order_id=body.razorpay_order_id,
        payment_id=body.razorpay_payment_id,
        signature=body.razorpay_signature,
        outcome=body.outcome,
        failure_reason=body.failure_reason,
    )
    pmap = await _plan_public_id_map(db)
    sub_out: StudentSubscriptionOut | None = None
    if active is not None:
        courses = await service.courses_for_subscription(active.id)
        sub_out = _sub_out(active, courses, pmap.get(active.plan_id))
    return VerifyPaymentResponse(
        message="Payment verified and subscription activated." if tx.status == "succeeded" else "Payment status updated.",
        transaction=_tx_out(tx, pmap.get(tx.plan_id)),
        subscription=sub_out,
    )


@student_router.post(
    "/payments/{tx_id}/test-callback",
    summary="Simulate signed gateway callback in test/local environments",
    responses=errors(*AUTHENTICATED, 403, 404),
    dependencies=[WriteRateLimit],
)
async def student_test_callback(
    tx_id: TxIdParam,
    body: TestGatewayCallbackRequest,
    auth: RequireIndependentStudent,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> VerifyPaymentResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    await service.sign_test_gateway_payment(
        auth,
        tx_id,
        outcome=body.outcome,
        payment_id=body.payment_id,
        failure_reason=body.failure_reason,
    )
    tx = await service.get_owned_transaction(auth.user_id, tx_id)
    active = await service.get_active_subscription(auth.user_id)
    pmap = await _plan_public_id_map(db)
    sub_out: StudentSubscriptionOut | None = None
    if active is not None:
        courses = await service.courses_for_subscription(active.id)
        sub_out = _sub_out(active, courses, pmap.get(active.plan_id))
    return VerifyPaymentResponse(
        message="Payment captured via verified test gateway callback." if tx.status == "succeeded" else "Payment marked failed.",
        transaction=_tx_out(tx, pmap.get(tx.plan_id)),
        subscription=sub_out,
    )


@student_router.get(
    "/payments/{tx_id}/status",
    response_model=VerifyPaymentResponse,
    summary="Poll current transaction and subscription activation status",
    responses=errors(*AUTHENTICATED, 404),
)
async def student_payment_status(
    tx_id: TxIdParam,
    auth: RequireIndependentStudent,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> VerifyPaymentResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    tx = await service.get_owned_transaction(auth.user_id, tx_id)
    active = await service.get_active_subscription(auth.user_id)
    pmap = await _plan_public_id_map(db)
    sub_out: StudentSubscriptionOut | None = None
    if active is not None:
        courses = await service.courses_for_subscription(active.id)
        sub_out = _sub_out(active, courses, pmap.get(active.plan_id))
    return VerifyPaymentResponse(
        message="",
        transaction=_tx_out(tx, pmap.get(tx.plan_id)),
        subscription=sub_out,
    )


@student_router.get("/payments", response_model=TransactionListResponse, summary="Student payment history", responses=errors(*AUTHENTICATED))
async def student_list_payments(
    auth: RequireIndependentStudent,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
    status: Annotated[str | None, Query()] = None,
    from_date: Annotated[str | None, Query()] = None,
    to_date: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TransactionListResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    rows, total = await service.list_transactions(
        user_id=auth.user_id,
        status=status,
        from_date=_parse_date_bound(from_date, end_of_day=False),
        to_date=_parse_date_bound(to_date, end_of_day=True),
        search=search,
        page=page,
        per_page=per_page,
    )
    pmap = await _plan_public_id_map(db)
    return TransactionListResponse(
        message="",
        transactions=[_tx_out(r, pmap.get(r.plan_id)) for r in rows],
        page_context=PageContext.build(page=page, per_page=per_page, total=total, is_exact=True, sort_column="created_at", sort_order=SortOrder.DESC),
    )


@student_router.get("/payments/{tx_id}/receipt", response_model=ReceiptResponse, summary="Get receipt / invoice details for a payment", responses=errors(*AUTHENTICATED, 404))
async def student_payment_receipt(
    tx_id: TxIdParam,
    auth: RequireIndependentStudent,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> ReceiptResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    tx = await service.get_owned_transaction(auth.user_id, tx_id)
    return ReceiptResponse(
        message="",
        receipt={
            "transaction_id": str(tx.public_id),
            "transaction_ref": tx.transaction_ref,
            "invoice_number": tx.invoice_number,
            "plan_name": tx.plan_name,
            "course_title": tx.course_title,
            "action_type": tx.action_type.value if hasattr(tx.action_type, "value") else str(tx.action_type),
            "original_amount_paise": tx.original_amount_paise,
            "discount_paise": tx.discount_paise,
            "tax_paise": tx.tax_paise,
            "total_amount_paise": tx.total_amount_paise,
            "currency": tx.currency,
            "payment_method": tx.payment_method,
            "gateway_order_id": tx.gateway_order_id,
            "gateway_payment_id": tx.gateway_payment_id,
            "status": tx.status.value if hasattr(tx.status, "value") else str(tx.status),
            "paid_at": tx.paid_at.isoformat() if tx.paid_at else None,
            "created_at": tx.created_at.isoformat(),
            "seller_name": settings.SELLER_LEGAL_NAME,
            "seller_gstin": settings.SELLER_GSTIN,
            "seller_state": settings.SELLER_STATE,
        },
    )


@student_router.get("/subscription", response_model=StudentSubscriptionOverviewResponse, summary="Active subscription, accessible courses, upgrade options & history", responses=errors(*AUTHENTICATED))
async def student_subscription_overview(
    auth: RequireStudentUser,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> StudentSubscriptionOverviewResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    ov = await service.overview_for_student(auth.user_id)
    pmap = await _plan_public_id_map(db)
    course_map = ov["course_map"]
    active = ov["active"]
    latest_tx = ov["latest_tx"]
    return StudentSubscriptionOverviewResponse(
        message="",
        active_subscription=_sub_out(active, course_map.get(active.id, []), pmap.get(active.plan_id)) if active else None,
        history=[_sub_out(s, course_map.get(s.id, []), pmap.get(s.plan_id)) for s in ov["history"]],
        available_upgrades=[_plan_out(p) for p in ov["upgrades"]],
        latest_payment=_tx_out(latest_tx, pmap.get(latest_tx.plan_id)) if latest_tx else None,
    )


@student_router.post(
    "/subscription/enroll-course",
    response_model=StudentSubscriptionOverviewResponse,
    summary="Unlock an approved course under current active subscription plan",
    responses=errors(*AUTHENTICATED, 403, 404, 409),
    dependencies=[WriteRateLimit],
)
async def student_enroll_course_under_plan(
    body: EnrollCourseUnderPlanRequest,
    auth: RequireIndependentStudent,
    db: DbSession,
    settings: SettingsDep,
    gateway: PaymentGatewayDep,
) -> StudentSubscriptionOverviewResponse:
    service = StudentSubscriptionService(db, settings, gateway)
    await service.enroll_course_under_plan(auth, int(body.course_id))
    ov = await service.overview_for_student(auth.user_id)
    pmap = await _plan_public_id_map(db)
    course_map = ov["course_map"]
    active = ov["active"]
    latest_tx = ov["latest_tx"]
    return StudentSubscriptionOverviewResponse(
        message="Course access granted under your active subscription.",
        active_subscription=_sub_out(active, course_map.get(active.id, []), pmap.get(active.plan_id)) if active else None,
        history=[_sub_out(s, course_map.get(s.id, []), pmap.get(s.plan_id)) for s in ov["history"]],
        available_upgrades=[_plan_out(p) for p in ov["upgrades"]],
        latest_payment=_tx_out(latest_tx, pmap.get(latest_tx.plan_id)) if latest_tx else None,
    )
