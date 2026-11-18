"""Institution-based & individual student payment workflows (requests, bulk/single checkout, RBAC, allocations)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.ids import new_public_id, parse_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import PaymentRequestStatus, PaymentScope, StudentSubStatus, TxActionType, TxStatus
from app.models.student_subscription import (
    PaymentSettings,
    StudentPaymentAllocation,
    StudentPaymentRequest,
    StudentPaymentTransaction,
    StudentSubscription,
    StudentSubscriptionCourse,
    SubscriptionPlan,
)
from app.services.cross_service_sync import (
    fetch_institution_head_user_ids,
    fetch_student_profile,
    list_institution_approved_courses,
    list_institution_students_from_um,
    resolve_student_category,
    send_in_app_notification,
    sync_student_course_enrollment,
    verify_course_eligible_for_student,
)
from app.services.student_subscription_service import StudentSubscriptionService


class InstitutionPaymentService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.base = StudentSubscriptionService(db, settings)

    # ------------------------------------------------------------------ category guards
    async def get_student_account_context(self, auth: AccessTokenClaims) -> dict[str, Any]:
        category = await resolve_student_category(self.settings, auth)
        return {
            "student_category": category,
            "can_pay_directly": category == "individual",
            "must_request_payment": category == "institution",
            "organization_id": auth.organization_id,
        }

    async def assert_independent_student(self, auth: AccessTokenClaims) -> None:
        category = await resolve_student_category(self.settings, auth)
        if category != "individual":
            raise PermissionDeniedError(
                "Institution-managed students cannot make direct payments. Submit a payment request to your Institution Head.",
                code="INSTITUTION_STUDENT_DIRECT_PAYMENT_FORBIDDEN",
            )

    async def assert_institution_student(self, auth: AccessTokenClaims) -> None:
        category = await resolve_student_category(self.settings, auth)
        if category != "institution" or not auth.organization_id:
            raise PermissionDeniedError(
                "Only institution-managed students can submit payment requests. Independent students pay directly.",
                code="INDEPENDENT_STUDENT_REQUEST_FORBIDDEN",
            )

    # ------------------------------------------------------------------ student payment requests
    async def create_payment_request(
        self,
        auth: AccessTokenClaims,
        *,
        course_id: int,
        plan_public_id: str,
        student_note: str | None = None,
    ) -> StudentPaymentRequest:
        await self.assert_institution_student(auth)
        plan = await self.base.get_plan(int(parse_public_id(plan_public_id) or 0))
        if not plan.is_active:
            raise ValidationFailedError(details=[{"field": "plan_id", "code": "INACTIVE", "message": "Plan is not active."}])

        course_info = await verify_course_eligible_for_student(self.settings, auth, course_id)

        # Prevent duplicate active subscription covering same plan + course
        active_sub = await self.base.get_active_subscription(auth.user_id)
        if active_sub and active_sub.plan_id == plan.id:
            existing_course = await self.db.scalar(
                select(StudentSubscriptionCourse).where(
                    StudentSubscriptionCourse.subscription_id == active_sub.id,
                    StudentSubscriptionCourse.course_id == int(course_id),
                )
            )
            if existing_course is not None:
                raise ConflictError("You already have an active subscription for this course and plan.", code="ALREADY_SUBSCRIBED")

        # Prevent duplicate open request
        open_statuses = (
            PaymentRequestStatus.PENDING,
            PaymentRequestStatus.APPROVED,
            PaymentRequestStatus.PAYMENT_INITIATED,
        )
        dup_req = await self.db.scalar(
            select(StudentPaymentRequest).where(
                StudentPaymentRequest.student_user_id == auth.user_id,
                StudentPaymentRequest.course_id == int(course_id),
                StudentPaymentRequest.plan_id == plan.id,
                StudentPaymentRequest.status.in_(open_statuses),
            )
        )
        if dup_req is not None:
            raise ConflictError(
                f"A payment request ({dup_req.request_ref}) is already {dup_req.status} for this course and plan.",
                code="DUPLICATE_PAYMENT_REQUEST",
            )

        profile = await fetch_student_profile(self.settings, auth.user_id)
        student_name = profile["name"] if profile else f"Student {auth.user_id}"
        student_email = profile["email"] if profile else ""

        req = StudentPaymentRequest(
            id=uuid.uuid4(),
            public_id=new_public_id(),
            request_ref=f"REQ-{utcnow().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}",
            student_user_id=auth.user_id,
            student_name=student_name,
            student_email=student_email,
            organization_id=int(auth.organization_id or 0),
            course_id=int(course_id),
            course_title=course_info["title"],
            plan_id=plan.id,
            plan_code=plan.code,
            plan_name=plan.name,
            amount_paise=plan.price_paise,
            status=PaymentRequestStatus.PENDING,
            student_note=student_note.strip() if student_note else None,
        )
        self.db.add(req)
        await self.db.commit()
        await self.db.refresh(req)

        for head_id in await fetch_institution_head_user_ids(self.settings, int(auth.organization_id or 0)):
            await send_in_app_notification(
                self.settings,
                recipient_user_id=head_id,
                organization_id=auth.organization_id,
                type_key="student.payment_request.created",
                title=f"New Payment Request: {student_name}",
                body=f"{student_name} requested {plan.name} for {course_info['title']} (₹{plan.price_paise // 100}).",
                data={"request_id": str(req.public_id), "course_id": str(course_id)},
            )
        return req

    async def list_student_payment_requests(
        self,
        auth: AccessTokenClaims,
        *,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[StudentPaymentRequest], int]:
        stmt = select(StudentPaymentRequest).where(StudentPaymentRequest.student_user_id == auth.user_id)
        count_stmt = select(func.count()).select_from(StudentPaymentRequest).where(StudentPaymentRequest.student_user_id == auth.user_id)
        if status:
            stmt = stmt.where(StudentPaymentRequest.status == status)
            count_stmt = count_stmt.where(StudentPaymentRequest.status == status)
        total = int((await self.db.execute(count_stmt)).scalar_one())
        rows = (
            await self.db.execute(
                stmt.order_by(StudentPaymentRequest.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
            )
        ).scalars().all()
        return list(rows), total

    async def cancel_payment_request(self, auth: AccessTokenClaims, request_public_id: int) -> StudentPaymentRequest:
        req = await self.db.scalar(
            select(StudentPaymentRequest).where(
                StudentPaymentRequest.public_id == request_public_id,
                StudentPaymentRequest.student_user_id == auth.user_id,
            )
        )
        if req is None:
            raise NotFoundError("Payment request not found.", code="PAYMENT_REQUEST_NOT_FOUND")
        if req.status != PaymentRequestStatus.PENDING:
            raise ConflictError(f"Cannot cancel a request with status '{req.status}'.", code="INVALID_REQUEST_STATE")
        req.status = PaymentRequestStatus.CANCELLED
        await self.db.commit()
        await self.db.refresh(req)
        return req

    # ------------------------------------------------------------------ institution head: students & requests
    async def list_institution_students(
        self,
        auth: AccessTokenClaims,
        *,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        org_id = int(auth.organization_id or 0)
        raw_students = await list_institution_students_from_um(self.settings, org_id, search=search)
        approved_courses = await list_institution_approved_courses(self.settings, org_id)

        total = len(raw_students)
        sliced = raw_students[(page - 1) * per_page : page * per_page]
        student_ids = [s["student_user_id"] for s in sliced]

        active_subs: dict[int, StudentSubscription] = {}
        latest_reqs: dict[int, StudentPaymentRequest] = {}
        if student_ids:
            subs = (
                await self.db.execute(
                    select(StudentSubscription)
                    .where(StudentSubscription.user_id.in_(student_ids), StudentSubscription.status == StudentSubStatus.ACTIVE)
                    .order_by(StudentSubscription.created_at.desc())
                )
            ).scalars().all()
            for sub in subs:
                active_subs.setdefault(sub.user_id, sub)

            reqs = (
                await self.db.execute(
                    select(StudentPaymentRequest)
                    .where(StudentPaymentRequest.student_user_id.in_(student_ids), StudentPaymentRequest.organization_id == org_id)
                    .order_by(StudentPaymentRequest.created_at.desc())
                )
            ).scalars().all()
            for r in reqs:
                latest_reqs.setdefault(r.student_user_id, r)

        items: list[dict[str, Any]] = []
        for s in sliced:
            uid = s["student_user_id"]
            sub = active_subs.get(uid)
            req = latest_reqs.get(uid)
            if sub:
                pay_status = "active_subscription"
            elif req and req.status == PaymentRequestStatus.PENDING:
                pay_status = "pending_request"
            elif req and req.status == PaymentRequestStatus.APPROVED:
                pay_status = "approved_request"
            elif req and req.status == PaymentRequestStatus.PAYMENT_INITIATED:
                pay_status = "payment_initiated"
            elif req and req.status == PaymentRequestStatus.FAILED:
                pay_status = "failed"
            else:
                pay_status = "unpaid"

            items.append(
                {
                    "student_user_id": str(uid),
                    "student_name": s["student_name"],
                    "student_email": s["student_email"],
                    "account_status": s["account_status"],
                    "selected_course_id": str(req.course_id) if req else None,
                    "selected_course_title": req.course_title if req else None,
                    "active_plan_name": sub.plan_name if sub else None,
                    "active_subscription_ends_at": sub.ends_at if sub else None,
                    "payment_status": pay_status,
                    "pending_request_id": str(req.public_id) if req and req.status in (PaymentRequestStatus.PENDING, PaymentRequestStatus.APPROVED) else None,
                    "pending_plan_id": str(req.plan_id) if req and req.status in (PaymentRequestStatus.PENDING, PaymentRequestStatus.APPROVED) else None,
                    "pending_plan_name": req.plan_name if req and req.status in (PaymentRequestStatus.PENDING, PaymentRequestStatus.APPROVED) else None,
                }
            )
        return {"students": items, "approved_courses": approved_courses, "total": total}

    async def assign_student_course(
        self,
        auth: AccessTokenClaims,
        *,
        student_user_id: int,
        course_id: int,
        plan_public_id: str | None = None,
    ) -> StudentPaymentRequest:
        org_id = int(auth.organization_id or 0)
        profile = await self._assert_student_belongs_to_institution(student_user_id, org_id)

        # Verify course is published and approved for this institution
        fake_student_claims = AccessTokenClaims(
            user_id=student_user_id,
            session_id=auth.session_id,
            role="student",
            organization_id=org_id,
            organization_type="institution",
            scopes=(),
            token_version=1,
            token_id=auth.token_id,
            issued_at=auth.issued_at,
            expires_at=auth.expires_at,
        )
        course_info = await verify_course_eligible_for_student(self.settings, fake_student_claims, course_id)

        if plan_public_id:
            plan = await self.base.get_plan(int(parse_public_id(plan_public_id) or 0))
        else:
            await self.base.ensure_defaults_seeded()
            plan = await self.db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.is_active.is_(True)).order_by(SubscriptionPlan.tier_rank.asc()).limit(1))
            if plan is None:
                raise NotFoundError("No active subscription plan available.", code="PLAN_NOT_FOUND")

        existing = await self.db.scalar(
            select(StudentPaymentRequest).where(
                StudentPaymentRequest.student_user_id == student_user_id,
                StudentPaymentRequest.organization_id == org_id,
                StudentPaymentRequest.course_id == int(course_id),
                StudentPaymentRequest.status.in_((PaymentRequestStatus.PENDING, PaymentRequestStatus.APPROVED)),
            )
        )
        if existing is not None:
            existing.plan_id = plan.id
            existing.plan_code = plan.code
            existing.plan_name = plan.name
            existing.amount_paise = plan.price_paise
            existing.status = PaymentRequestStatus.APPROVED
            existing.reviewed_by_user_id = auth.user_id
            existing.reviewed_at = utcnow()
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        req = StudentPaymentRequest(
            id=uuid.uuid4(),
            public_id=new_public_id(),
            request_ref=f"REQ-{utcnow().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}",
            student_user_id=student_user_id,
            student_name=profile["name"],
            student_email=profile["email"],
            organization_id=org_id,
            course_id=int(course_id),
            course_title=course_info["title"],
            plan_id=plan.id,
            plan_code=plan.code,
            plan_name=plan.name,
            amount_paise=plan.price_paise,
            status=PaymentRequestStatus.APPROVED,
            decision_note="Assigned by Institution Head (pending payment)",
            reviewed_by_user_id=auth.user_id,
            reviewed_at=utcnow(),
        )
        self.db.add(req)
        await self.db.commit()
        await self.db.refresh(req)
        return req

    async def list_institution_requests(
        self,
        auth: AccessTokenClaims,
        *,
        status: str | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[StudentPaymentRequest], int]:
        org_id = int(auth.organization_id or 0)
        stmt = select(StudentPaymentRequest).where(StudentPaymentRequest.organization_id == org_id)
        count_stmt = select(func.count()).select_from(StudentPaymentRequest).where(StudentPaymentRequest.organization_id == org_id)
        if status:
            stmt = stmt.where(StudentPaymentRequest.status == status)
            count_stmt = count_stmt.where(StudentPaymentRequest.status == status)
        if search:
            like = f"%{search.strip()}%"
            cond = (
                StudentPaymentRequest.student_name.ilike(like)
                | StudentPaymentRequest.student_email.ilike(like)
                | StudentPaymentRequest.request_ref.ilike(like)
                | StudentPaymentRequest.course_title.ilike(like)
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)
        total = int((await self.db.execute(count_stmt)).scalar_one())
        rows = (
            await self.db.execute(
                stmt.order_by(StudentPaymentRequest.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
            )
        ).scalars().all()
        return list(rows), total

    async def approve_request(self, auth: AccessTokenClaims, request_public_id: int, decision_note: str | None = None) -> StudentPaymentRequest:
        org_id = int(auth.organization_id or 0)
        req = await self._get_org_request(request_public_id, org_id)
        if req.status not in (PaymentRequestStatus.PENDING, PaymentRequestStatus.APPROVED):
            raise ConflictError(f"Cannot approve request in status '{req.status}'.", code="INVALID_REQUEST_STATE")
        req.status = PaymentRequestStatus.APPROVED
        req.decision_note = decision_note
        req.reviewed_by_user_id = auth.user_id
        req.reviewed_at = utcnow()
        await self.db.commit()
        await self.db.refresh(req)

        await send_in_app_notification(
            self.settings,
            recipient_user_id=req.student_user_id,
            organization_id=org_id,
            type_key="student.payment_request.approved",
            title="Payment Request Approved",
            body=f"Your payment request {req.request_ref} for {req.course_title} ({req.plan_name}) was approved. Payment is being processed by your Institution Head.",
            data={"request_id": str(req.public_id)},
        )
        return req

    async def reject_request(self, auth: AccessTokenClaims, request_public_id: int, decision_note: str | None = None) -> StudentPaymentRequest:
        org_id = int(auth.organization_id or 0)
        req = await self._get_org_request(request_public_id, org_id)
        if req.status in (PaymentRequestStatus.PAID, PaymentRequestStatus.CANCELLED):
            raise ConflictError(f"Cannot reject request in status '{req.status}'.", code="INVALID_REQUEST_STATE")
        req.status = PaymentRequestStatus.REJECTED
        req.decision_note = decision_note or "Rejected by Institution Head"
        req.reviewed_by_user_id = auth.user_id
        req.reviewed_at = utcnow()
        await self.db.commit()
        await self.db.refresh(req)

        await send_in_app_notification(
            self.settings,
            recipient_user_id=req.student_user_id,
            organization_id=org_id,
            type_key="student.payment_request.rejected",
            title="Payment Request Rejected",
            body=f"Your payment request {req.request_ref} was rejected.{f' Reason: {req.decision_note}' if req.decision_note else ''}",
            data={"request_id": str(req.public_id)},
        )
        return req

    # ------------------------------------------------------------------ institution head: bulk/single checkout
    async def preview_institution_checkout(
        self,
        auth: AccessTokenClaims,
        *,
        student_ids: list[int],
        plan_public_id: str,
        course_id: int | None = None,
        request_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        org_id = int(auth.organization_id or 0)
        if org_id <= 0:
            raise PermissionDeniedError("Institution context is required.", code="INSTITUTION_REQUIRED")

        settings_row = await self.base.get_payment_settings()
        plan = await self.base.get_plan(int(parse_public_id(plan_public_id) or 0))
        if not plan.is_active:
            raise ValidationFailedError(details=[{"field": "plan_id", "code": "INACTIVE", "message": "Selected plan is inactive."}])

        unique_students = list(dict.fromkeys(int(s) for s in student_ids))
        if not unique_students:
            raise ValidationFailedError(details=[{"field": "student_ids", "code": "EMPTY", "message": "Select at least one student."}])

        req_by_student: dict[int, StudentPaymentRequest] = {}
        if request_ids:
            parsed_req_ids = [parse_public_id(r) for r in request_ids]
            if any(p is None for p in parsed_req_ids):
                raise NotFoundError("One or more payment requests were not found.", code="PAYMENT_REQUEST_NOT_FOUND")
            reqs = (
                await self.db.execute(
                    select(StudentPaymentRequest).where(StudentPaymentRequest.public_id.in_([int(p) for p in parsed_req_ids if p is not None]))
                )
            ).scalars().all()
            if len(reqs) != len(parsed_req_ids):
                raise NotFoundError("One or more payment requests were not found.", code="PAYMENT_REQUEST_NOT_FOUND")
            for req in reqs:
                if req.organization_id != org_id:
                    raise PermissionDeniedError("Cannot access payment requests belonging to another institution.", code="CROSS_INSTITUTION_FORBIDDEN")
                if req.status not in (PaymentRequestStatus.PENDING, PaymentRequestStatus.APPROVED):
                    raise ConflictError(f"Request {req.request_ref} is already '{req.status}'.", code="INVALID_REQUEST_STATE")
                req_by_student[req.student_user_id] = req

        course_title: str | None = None
        if course_id is not None:
            fake_claims = AccessTokenClaims(
                user_id=auth.user_id,
                session_id=auth.session_id,
                role="student",
                organization_id=org_id,
                organization_type="institution",
                scopes=(),
                token_version=1,
                token_id=auth.token_id,
                issued_at=auth.issued_at,
                expires_at=auth.expires_at,
            )
            course_info = await verify_course_eligible_for_student(self.settings, fake_claims, course_id)
            course_title = course_info["title"]

        allocations: list[dict[str, Any]] = []
        original_total = 0
        discount_total = 0
        tax_total = 0
        grand_total = 0

        for sid in unique_students:
            profile = await self._assert_student_belongs_to_institution(sid, org_id)
            linked_req = req_by_student.get(sid)
            eff_course_id = linked_req.course_id if linked_req else course_id
            eff_course_title = linked_req.course_title if linked_req else course_title

            # Prevent duplicate active subscription for same plan + course, or duplicate pending allocation
            await self._ensure_no_duplicate_allocation(sid, plan.id, eff_course_id)

            active_sub = await self.base.get_active_subscription(sid)
            orig = plan.price_paise
            disc = 0
            if active_sub and settings_row.upgrade_pricing_mode == "price_difference" and active_sub.plan_id != plan.id:
                disc = min(orig, active_sub.price_paise)
            net = max(0, orig - disc)
            tax = round(net * max(0, settings_row.tax_rate_percent) / 100)
            total = net + tax

            original_total += orig
            discount_total += disc
            tax_total += tax
            grand_total += total

            allocations.append(
                {
                    "student_user_id": str(sid),
                    "student_name": profile["name"],
                    "student_email": profile["email"],
                    "course_id": str(eff_course_id) if eff_course_id else None,
                    "course_title": eff_course_title,
                    "payment_request_id": str(linked_req.public_id) if linked_req else None,
                    "original_amount_paise": orig,
                    "discount_paise": disc,
                    "tax_paise": tax,
                    "total_amount_paise": total,
                    "_req_obj": linked_req,
                }
            )

        return {
            "plan": plan,
            "student_count": len(allocations),
            "currency": "INR",
            "original_total_paise": original_total,
            "discount_total_paise": discount_total,
            "tax_rate_percent": settings_row.tax_rate_percent,
            "tax_total_paise": tax_total,
            "grand_total_paise": grand_total,
            "allocations": allocations,
            "accepted_methods": settings_row.accepted_methods or {},
            "payments_enabled": settings_row.payments_enabled,
        }

    async def create_institution_checkout(
        self,
        auth: AccessTokenClaims,
        *,
        student_ids: list[int],
        plan_public_id: str,
        payment_method: str,
        course_id: int | None = None,
        request_ids: list[str] | None = None,
    ) -> tuple[StudentPaymentTransaction, list[StudentPaymentAllocation], dict[str, Any]]:
        summary = await self.preview_institution_checkout(
            auth,
            student_ids=student_ids,
            plan_public_id=plan_public_id,
            course_id=course_id,
            request_ids=request_ids,
        )
        if not summary["payments_enabled"]:
            raise PermissionDeniedError("Course payments are currently disabled by the administrator.", code="PAYMENTS_DISABLED")
        accepted = summary["accepted_methods"]
        method_key = "upi" if payment_method in ("upi", "gpay", "phonepe", "paytm") else payment_method
        if accepted and accepted.get(method_key) is False and accepted.get(payment_method) is False:
            raise ValidationFailedError(details=[{"field": "payment_method", "code": "METHOD_DISABLED", "message": "Selected payment method is disabled."}])

        org_id = int(auth.organization_id or 0)
        plan: SubscriptionPlan = summary["plan"]
        settings_row = await self.base.get_payment_settings()
        count = summary["student_count"]
        scope = PaymentScope.INSTITUTION_SINGLE if count == 1 else PaymentScope.INSTITUTION_BULK
        first_sid = int(summary["allocations"][0]["student_user_id"])

        order_id = f"order_inst_{secrets.token_hex(8)}"
        tx_ref = f"TXN-INST-{utcnow().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
        expires_at = utcnow() + timedelta(minutes=10)
        amount_rupees = f"{summary['grand_total_paise'] / 100:.2f}"
        upi_qr = (
            f"upi://pay?pa={settings_row.upi_vpa}&pn={settings_row.upi_merchant_name}"
            f"&am={amount_rupees}&cu=INR&tr={tx_ref}&tn={plan.name.replace(' ', '+')}"
        )

        tx = StudentPaymentTransaction(
            id=uuid.uuid4(),
            public_id=new_public_id(),
            transaction_ref=tx_ref,
            user_id=first_sid,
            payer_user_id=auth.user_id,
            payer_role="institution_head",
            payment_scope=scope,
            student_count=count,
            organization_id=org_id,
            subscription_id=None,
            plan_id=plan.id,
            plan_code=plan.code,
            plan_name=plan.name,
            course_id=course_id,
            course_title=summary["allocations"][0]["course_title"] if count == 1 else f"{count} Students",
            action_type=TxActionType.NEW,
            original_amount_paise=summary["original_total_paise"],
            discount_paise=summary["discount_total_paise"],
            tax_paise=summary["tax_total_paise"],
            total_amount_paise=summary["grand_total_paise"],
            currency="INR",
            payment_method=payment_method,
            gateway_provider="razorpay" if self.settings.RAZORPAY_KEY_ID else "test_gateway",
            gateway_order_id=order_id,
            upi_qr_payload=upi_qr,
            status=TxStatus.PENDING,
            expires_at=expires_at,
        )
        self.db.add(tx)
        await self.db.flush()

        alloc_rows: list[StudentPaymentAllocation] = []
        for item in summary["allocations"]:
            req_obj: StudentPaymentRequest | None = item.get("_req_obj")
            alloc = StudentPaymentAllocation(
                id=uuid.uuid4(),
                public_id=new_public_id(),
                transaction_id=tx.id,
                organization_id=org_id,
                payer_user_id=auth.user_id,
                student_user_id=int(item["student_user_id"]),
                student_name=item["student_name"],
                student_email=item["student_email"],
                course_id=int(item["course_id"]) if item["course_id"] else None,
                course_title=item["course_title"],
                plan_id=plan.id,
                plan_code=plan.code,
                plan_name=plan.name,
                payment_request_id=req_obj.id if req_obj else None,
                original_amount_paise=item["original_amount_paise"],
                discount_paise=item["discount_paise"],
                tax_paise=item["tax_paise"],
                allocated_amount_paise=item["total_amount_paise"],
                status=TxStatus.PENDING,
            )
            self.db.add(alloc)
            alloc_rows.append(alloc)
            if req_obj is not None:
                req_obj.status = PaymentRequestStatus.PAYMENT_INITIATED
                req_obj.reviewed_by_user_id = req_obj.reviewed_by_user_id or auth.user_id
                req_obj.reviewed_at = req_obj.reviewed_at or utcnow()
                req_obj.transaction_id = tx.id
                req_obj.allocation_id = alloc.id

        await self.db.commit()
        await self.db.refresh(tx)
        for a in alloc_rows:
            await self.db.refresh(a)

        gateway_payload = {
            "provider": tx.gateway_provider,
            "test_mode": True,
            "key_id": self.settings.RAZORPAY_KEY_ID or "rzp_test_examlms",
            "order_id": order_id,
            "amount": tx.total_amount_paise,
            "currency": "INR",
            "seller_name": settings_row.upi_merchant_name,
            "upi_qr_payload": upi_qr,
            "expires_at": expires_at,
        }
        return tx, alloc_rows, gateway_payload

    async def verify_institution_payment(
        self,
        auth: AccessTokenClaims,
        tx_public_id: int,
        *,
        razorpay_order_id: str | None = None,
        razorpay_payment_id: str | None = None,
        razorpay_signature: str | None = None,
        outcome: str = "succeeded",
        failure_reason: str | None = None,
    ) -> tuple[StudentPaymentTransaction, list[StudentPaymentAllocation]]:
        org_id = int(auth.organization_id or 0)
        tx = await self.db.scalar(
            select(StudentPaymentTransaction).where(
                StudentPaymentTransaction.public_id == tx_public_id,
                StudentPaymentTransaction.organization_id == org_id,
                StudentPaymentTransaction.payer_role == "institution_head",
            )
        )
        if tx is None:
            raise NotFoundError("Institution payment transaction not found.", code="TRANSACTION_NOT_FOUND")

        if tx.status == TxStatus.SUCCEEDED:
            allocs = await self._get_tx_allocations(tx.id)
            return tx, allocs

        if outcome == "failed":
            return await self._fail_institution_transaction(tx, failure_reason or "Payment failed or cancelled by Institution Head.")

        if outcome == "pending":
            tx.status = TxStatus.PENDING
            await self.db.commit()
            return tx, await self._get_tx_allocations(tx.id)

        secret = self.settings.RAZORPAY_KEY_SECRET.get_secret_value() or "examlms-test-secret"
        if razorpay_order_id and razorpay_order_id != tx.gateway_order_id:
            raise BadRequestError("Order ID mismatch.", code="ORDER_MISMATCH")
        if razorpay_payment_id and razorpay_signature:
            expected = hmac.new(secret.encode(), f"{tx.gateway_order_id}|{razorpay_payment_id}".encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, razorpay_signature):
                await self._fail_institution_transaction(tx, "Invalid payment signature.")
                raise BadRequestError("Invalid payment signature.", code="INVALID_SIGNATURE")
        elif not self.settings.RAZORPAY_KEY_ID:
            razorpay_payment_id = razorpay_payment_id or f"pay_test_{secrets.token_hex(6)}"
            razorpay_signature = hmac.new(secret.encode(), f"{tx.gateway_order_id}|{razorpay_payment_id}".encode(), hashlib.sha256).hexdigest()
        else:
            raise BadRequestError("Missing gateway payment verification signature.", code="INVALID_SIGNATURE")

        return await self._activate_institution_transaction(tx, payment_id=razorpay_payment_id, signature=razorpay_signature, paid_by=auth.user_id)

    async def test_callback_institution_payment(
        self,
        auth: AccessTokenClaims,
        tx_public_id: int,
        *,
        outcome: str,
        payment_id: str | None = None,
        failure_reason: str | None = None,
    ) -> tuple[StudentPaymentTransaction, list[StudentPaymentAllocation]]:
        org_id = int(auth.organization_id or 0)
        tx = await self.db.scalar(
            select(StudentPaymentTransaction).where(
                StudentPaymentTransaction.public_id == tx_public_id,
                StudentPaymentTransaction.organization_id == org_id,
                StudentPaymentTransaction.payer_role == "institution_head",
            )
        )
        if tx is None:
            raise NotFoundError("Institution payment transaction not found.", code="TRANSACTION_NOT_FOUND")

        if outcome == "failed":
            return await self._fail_institution_transaction(tx, failure_reason or "Gateway reported payment failure.")

        pid = payment_id or f"pay_test_{secrets.token_hex(6)}"
        secret = self.settings.RAZORPAY_KEY_SECRET.get_secret_value() or "examlms-test-secret"
        sig = hmac.new(secret.encode(), f"{tx.gateway_order_id}|{pid}".encode(), hashlib.sha256).hexdigest()
        return await self._activate_institution_transaction(tx, payment_id=pid, signature=sig, paid_by=auth.user_id)

    async def _activate_institution_transaction(
        self,
        tx: StudentPaymentTransaction,
        *,
        payment_id: str,
        signature: str | None,
        paid_by: int,
    ) -> tuple[StudentPaymentTransaction, list[StudentPaymentAllocation]]:
        if tx.status == TxStatus.SUCCEEDED:
            return tx, await self._get_tx_allocations(tx.id)

        plan = await self.db.scalar(select(SubscriptionPlan).where(SubscriptionPlan.id == tx.plan_id))
        if plan is None:
            raise NotFoundError("Subscription plan not found.", code="PLAN_NOT_FOUND")

        now = utcnow()
        tx.status = TxStatus.SUCCEEDED
        tx.gateway_payment_id = payment_id
        tx.gateway_signature = signature
        tx.paid_at = now
        tx.failure_reason = None

        allocs = await self._get_tx_allocations(tx.id)
        sync_targets: list[tuple[int, int, str]] = []
        notify_targets: list[tuple[int, str, str]] = []

        for alloc in allocs:
            # Supersede student's previous active subscription if any
            prev_active = await self.base.get_active_subscription(alloc.student_user_id)
            if prev_active is not None:
                prev_active.status = StudentSubStatus.SUPERSEDED

            sub = StudentSubscription(
                id=uuid.uuid4(),
                public_id=new_public_id(),
                user_id=alloc.student_user_id,
                organization_id=alloc.organization_id,
                plan_id=plan.id,
                plan_code=plan.code,
                plan_name=plan.name,
                price_paise=plan.price_paise,
                duration_days=plan.billing_duration_days,
                max_courses=plan.max_courses,
                features_snapshot=list(plan.features or []),
                assessment_access_snapshot=dict(plan.assessment_access or {}),
                certificate_level=plan.certificate_level,
                status=StudentSubStatus.ACTIVE,
                starts_at=now,
                ends_at=now + timedelta(days=plan.billing_duration_days),
                replaced_subscription_id=prev_active.id if prev_active else None,
            )
            self.db.add(sub)
            await self.db.flush()

            alloc.subscription_id = sub.id
            alloc.status = TxStatus.SUCCEEDED
            alloc.activated_at = now

            if tx.subscription_id is None:
                tx.subscription_id = sub.id

            if alloc.course_id is not None:
                self.db.add(
                    StudentSubscriptionCourse(
                        id=uuid.uuid4(),
                        subscription_id=sub.id,
                        user_id=alloc.student_user_id,
                        course_id=int(alloc.course_id),
                        course_title=alloc.course_title or f"Course {alloc.course_id}",
                        granted_at=now,
                    )
                )
                sync_targets.append((alloc.student_user_id, int(alloc.course_id), alloc.course_title or f"Course {alloc.course_id}"))

            if alloc.payment_request_id is not None:
                req = await self.db.scalar(select(StudentPaymentRequest).where(StudentPaymentRequest.id == alloc.payment_request_id))
                if req is not None:
                    req.status = PaymentRequestStatus.PAID
                    req.paid_by_user_id = paid_by
                    req.paid_at = now
                    req.transaction_id = tx.id
                    req.allocation_id = alloc.id

            notify_targets.append((alloc.student_user_id, alloc.course_title or plan.name, plan.name))

        await self.db.commit()
        await self.db.refresh(tx)

        for sid, cid, ctitle in sync_targets:
            await sync_student_course_enrollment(
                self.settings,
                user_id=sid,
                organization_id=tx.organization_id,
                course_id=cid,
                course_title=ctitle,
                starts_at=now,
                ends_at=now + timedelta(days=plan.billing_duration_days),
            )

        for sid, label, plan_name in notify_targets:
            await send_in_app_notification(
                self.settings,
                recipient_user_id=sid,
                organization_id=tx.organization_id,
                type_key="student.payment.activated",
                title="Subscription Activated",
                body=f"Your Institution Head completed payment for {plan_name} ({label}). Course access is now unlocked.",
                data={"tx_id": str(tx.public_id)},
            )

        return tx, await self._get_tx_allocations(tx.id)

    async def _fail_institution_transaction(
        self,
        tx: StudentPaymentTransaction,
        reason: str,
    ) -> tuple[StudentPaymentTransaction, list[StudentPaymentAllocation]]:
        tx.status = TxStatus.FAILED
        tx.failure_reason = reason[:300]
        allocs = await self._get_tx_allocations(tx.id)
        notify_ids: list[int] = []
        for alloc in allocs:
            alloc.status = TxStatus.FAILED
            if alloc.payment_request_id is not None:
                req = await self.db.scalar(select(StudentPaymentRequest).where(StudentPaymentRequest.id == alloc.payment_request_id))
                if req is not None and req.status != PaymentRequestStatus.PAID:
                    req.status = PaymentRequestStatus.FAILED
            notify_ids.append(alloc.student_user_id)
        await self.db.commit()
        await self.db.refresh(tx)

        for sid in notify_ids:
            await send_in_app_notification(
                self.settings,
                recipient_user_id=sid,
                organization_id=tx.organization_id,
                type_key="student.payment.failed",
                title="Institution Payment Failed",
                body=f"Payment attempt {tx.transaction_ref} failed: {tx.failure_reason}",
                data={"tx_id": str(tx.public_id)},
            )
        return tx, allocs

    async def list_institution_transactions(
        self,
        auth: AccessTokenClaims,
        *,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[StudentPaymentTransaction], int]:
        org_id = int(auth.organization_id or 0)
        stmt = select(StudentPaymentTransaction).where(
            StudentPaymentTransaction.organization_id == org_id,
            StudentPaymentTransaction.payer_role == "institution_head",
        )
        count_stmt = select(func.count()).select_from(StudentPaymentTransaction).where(
            StudentPaymentTransaction.organization_id == org_id,
            StudentPaymentTransaction.payer_role == "institution_head",
        )
        if status:
            stmt = stmt.where(StudentPaymentTransaction.status == status)
            count_stmt = count_stmt.where(StudentPaymentTransaction.status == status)
        total = int((await self.db.execute(count_stmt)).scalar_one())
        rows = (
            await self.db.execute(
                stmt.order_by(StudentPaymentTransaction.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
            )
        ).scalars().all()
        return list(rows), total

    async def get_institution_transaction_detail(
        self,
        auth: AccessTokenClaims,
        tx_public_id: int,
    ) -> tuple[StudentPaymentTransaction, list[StudentPaymentAllocation]]:
        org_id = int(auth.organization_id or 0)
        tx = await self.db.scalar(
            select(StudentPaymentTransaction).where(
                StudentPaymentTransaction.public_id == tx_public_id,
                StudentPaymentTransaction.organization_id == org_id,
            )
        )
        if tx is None:
            raise NotFoundError("Transaction not found.", code="TRANSACTION_NOT_FOUND")
        return tx, await self._get_tx_allocations(tx.id)

    async def list_institution_allocations(
        self,
        auth: AccessTokenClaims,
        *,
        student_user_id: int | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[StudentPaymentAllocation], int]:
        org_id = int(auth.organization_id or 0)
        stmt = select(StudentPaymentAllocation).where(StudentPaymentAllocation.organization_id == org_id)
        count_stmt = select(func.count()).select_from(StudentPaymentAllocation).where(StudentPaymentAllocation.organization_id == org_id)
        if student_user_id is not None:
            stmt = stmt.where(StudentPaymentAllocation.student_user_id == student_user_id)
            count_stmt = count_stmt.where(StudentPaymentAllocation.student_user_id == student_user_id)
        total = int((await self.db.execute(count_stmt)).scalar_one())
        rows = (
            await self.db.execute(
                stmt.order_by(StudentPaymentAllocation.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
            )
        ).scalars().all()
        return list(rows), total

    # ------------------------------------------------------------------ helpers
    async def _get_org_request(self, request_public_id: int, org_id: int) -> StudentPaymentRequest:
        req = await self.db.scalar(select(StudentPaymentRequest).where(StudentPaymentRequest.public_id == request_public_id))
        if req is None:
            raise NotFoundError("Payment request not found.", code="PAYMENT_REQUEST_NOT_FOUND")
        if req.organization_id != org_id:
            raise PermissionDeniedError("Cannot access payment requests from another institution.", code="CROSS_INSTITUTION_FORBIDDEN")
        return req

    async def _assert_student_belongs_to_institution(self, student_user_id: int, org_id: int) -> dict[str, Any]:
        profile = await fetch_student_profile(self.settings, student_user_id)
        if profile is None:
            raise NotFoundError(f"Student {student_user_id} not found.", code="STUDENT_NOT_FOUND")
        if profile["role"] != "student":
            raise ValidationFailedError(details=[{"field": "student_ids", "code": "NOT_A_STUDENT", "message": f"User {student_user_id} is not a student."}])
        if profile["organization_id"] is not None and int(profile["organization_id"]) != int(org_id):
            raise PermissionDeniedError(
                "You cannot access or pay for students belonging to another institution.",
                code="CROSS_INSTITUTION_STUDENT_FORBIDDEN",
            )
        return profile

    async def _ensure_no_duplicate_allocation(self, student_user_id: int, plan_id: uuid.UUID, course_id: int | None) -> None:
        pending_alloc = await self.db.scalar(
            select(StudentPaymentAllocation).where(
                StudentPaymentAllocation.student_user_id == student_user_id,
                StudentPaymentAllocation.plan_id == plan_id,
                StudentPaymentAllocation.status == TxStatus.PENDING,
            )
        )
        if pending_alloc is not None:
            raise ConflictError(
                f"A pending payment allocation already exists for student {student_user_id}.",
                code="DUPLICATE_PENDING_ALLOCATION",
            )
        active_sub = await self.base.get_active_subscription(student_user_id)
        if active_sub and active_sub.plan_id == plan_id:
            if course_id is None:
                raise ConflictError(
                    f"Student {student_user_id} already has an active {active_sub.plan_name} subscription.",
                    code="DUPLICATE_ACTIVE_SUBSCRIPTION",
                )
            course_row = await self.db.scalar(
                select(StudentSubscriptionCourse).where(
                    StudentSubscriptionCourse.subscription_id == active_sub.id,
                    StudentSubscriptionCourse.course_id == int(course_id),
                )
            )
            if course_row is not None:
                raise ConflictError(
                    f"Student {student_user_id} already has active access to this course under {active_sub.plan_name}.",
                    code="DUPLICATE_COURSE_ALLOCATION",
                )

    async def _get_tx_allocations(self, tx_id: uuid.UUID) -> list[StudentPaymentAllocation]:
        rows = (
            await self.db.execute(
                select(StudentPaymentAllocation)
                .where(StudentPaymentAllocation.transaction_id == tx_id)
                .order_by(StudentPaymentAllocation.created_at.asc())
            )
        ).scalars().all()
        return list(rows)
