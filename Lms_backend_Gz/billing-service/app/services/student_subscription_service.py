"""Student subscription plans, payment settings, checkout, signature/webhook verification, upgrades, renewals, and history."""

from datetime import UTC, datetime, timedelta
import hmac
import secrets
from typing import Any
from urllib.parse import quote
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import tax
from app.core.config import Settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, PermissionDeniedError, UpstreamUnavailableError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import InvoiceKind, InvoiceStatus, PaymentRequestStatus, PaymentScope, StudentSubStatus, TxActionType, TxStatus
from app.gateways.errors import Rejected, Unavailable
from app.gateways.payment import PaymentGateway, PaymentGatewayNotConfigured, sign
from app.models.billing import Invoice
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
    fetch_institution_names,
    resolve_student_category,
    sync_student_course_enrollment,
    verify_course_eligible_for_student,
)
from app.services.invoice_service import InvoiceService
from app.services.outbox import write_event

DEFAULT_PLANS: tuple[dict[str, Any], ...] = (
    {
        "code": "base",
        "name": "Base Plan",
        "description": "Essential learning access for getting started.",
        "price_paise": 49900,
        "min_price_paise": 49900,
        "max_price_paise": 499900,
        "billing_duration_days": 30,
        "billing_label": "month",
        "max_courses": 5,
        "features": [
            "Access to 5 courses",
            "Chapter Tests",
            "Basic Certificate",
            "Email Support",
        ],
        "course_access_rules": {"all_approved_courses": True, "course_ids": []},
        "assessment_access": {"chapter_tests": True, "module_tests": False, "final_exam": False, "proctoring": False},
        "certificate_level": "basic",
        "support_tier": "Email Support",
        "is_active": True,
        "is_recommended": False,
        "display_order": 1,
        "tier_rank": 1,
    },
    {
        "code": "silver",
        "name": "Silver Plan",
        "description": "More learning with chapter and module assessments.",
        "price_paise": 99900,
        "min_price_paise": 49900,
        "max_price_paise": 499900,
        "billing_duration_days": 30,
        "billing_label": "month",
        "max_courses": 15,
        "features": [
            "Access to 15 courses",
            "Module & Chapter Tests",
            "Premium Certificate",
            "Priority Support",
        ],
        "course_access_rules": {"all_approved_courses": True, "course_ids": []},
        "assessment_access": {"chapter_tests": True, "module_tests": True, "final_exam": False, "proctoring": False},
        "certificate_level": "premium",
        "support_tier": "Priority Support",
        "is_active": True,
        "is_recommended": True,
        "display_order": 2,
        "tier_rank": 2,
    },
    {
        "code": "gold",
        "name": "Gold Plan",
        "description": "Unlimited learning access with proctored final exams.",
        "price_paise": 149900,
        "min_price_paise": 49900,
        "max_price_paise": 499900,
        "billing_duration_days": 30,
        "billing_label": "month",
        "max_courses": None,
        "features": [
            "Access to All Courses",
            "Final Exam with Proctoring",
            "Premium Certificate",
            "24/7 Support",
        ],
        "course_access_rules": {"all_approved_courses": True, "course_ids": []},
        "assessment_access": {"chapter_tests": True, "module_tests": True, "final_exam": True, "proctoring": True},
        "certificate_level": "pro",
        "support_tier": "24/7 Support",
        "is_active": True,
        "is_recommended": False,
        "display_order": 3,
        "tier_rank": 3,
    },
)

DEFAULT_ACCEPTED_METHODS: dict[str, bool] = {
    "razorpay": True,
    "stripe": False,
    "upi": True,
    "cards": True,
    "netbanking": True,
    "wallet": True,
}

_METHOD_TO_SETTING_KEY: dict[str, str] = {
    "upi": "upi",
    "gpay": "upi",
    "phonepe": "upi",
    "paytm": "upi",
    "card": "cards",
    "cards": "cards",
    "netbanking": "netbanking",
    "wallet": "wallet",
    "razorpay": "razorpay",
    "stripe": "stripe",
}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class StudentSubscriptionService:
    def __init__(self, db: AsyncSession, settings: Settings, gateway: PaymentGateway | None = None) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway or PaymentGateway(settings)
        self.invoices = InvoiceService(db, settings)

    # ------------------------------------------------------------------ gateway secrets & mode
    @property
    def is_test_mode(self) -> bool:
        if self.gateway.configured:
            key = self.settings.RAZORPAY_KEY_ID or ""
            return key.startswith("rzp_test_") or not self.settings.is_production_like
        return not self.settings.is_production_like

    def _checkout_secret(self) -> str:
        rzp_secret = self.settings.RAZORPAY_KEY_SECRET.get_secret_value()
        if self.gateway.configured and rzp_secret:
            return rzp_secret
        return self.settings.PAYMENT_WEBHOOK_SECRET.get_secret_value()

    def _checkout_key_id(self) -> str | None:
        if self.gateway.public_key:
            return self.gateway.public_key
        if not self.settings.is_production_like:
            return "rzp_test_examlms"
        return None

    # ------------------------------------------------------------------ seeding & settings
    async def ensure_defaults(self) -> None:
        settings_row = await self.db.get(PaymentSettings, 1)
        changed = False
        if settings_row is None:
            settings_row = PaymentSettings(
                id=1,
                payments_enabled=True,
                min_amount_paise=49900,
                max_amount_paise=499900,
                accepted_methods=dict(DEFAULT_ACCEPTED_METHODS),
                tax_rate_percent=0,
                upgrade_pricing_mode="price_difference",
                upi_vpa="examlms@icici",
                upi_merchant_name="ExamLMS",
            )
            self.db.add(settings_row)
            changed = True

        count = int((await self.db.execute(select(func.count()).select_from(SubscriptionPlan))).scalar_one())
        if count == 0:
            for item in DEFAULT_PLANS:
                self.db.add(SubscriptionPlan(public_id=new_public_id(), **item))
            changed = True

        if changed:
            await self.db.commit()

    async def get_payment_settings(self) -> PaymentSettings:
        await self.ensure_defaults()
        row = await self.db.get(PaymentSettings, 1)
        assert row is not None
        return row

    async def update_payment_settings(self, auth: AccessTokenClaims, payload: dict[str, Any]) -> PaymentSettings:
        row = await self.get_payment_settings()
        min_amt = int(payload["min_amount_paise"])
        max_amt = int(payload["max_amount_paise"])
        if max_amt < min_amt:
            raise BadRequestError("Maximum amount must be greater than or equal to minimum amount.", code="INVALID_PAYMENT_RANGE")
        row.payments_enabled = bool(payload["payments_enabled"])
        row.min_amount_paise = min_amt
        row.max_amount_paise = max_amt
        row.accepted_methods = {str(k): bool(v) for k, v in dict(payload["accepted_methods"]).items()}
        row.tax_rate_percent = int(payload["tax_rate_percent"])
        row.upgrade_pricing_mode = str(payload["upgrade_pricing_mode"])
        row.upi_vpa = str(payload["upi_vpa"]).strip()
        row.upi_merchant_name = str(payload["upi_merchant_name"]).strip()
        row.updated_by = auth.user_id
        await self.db.commit()
        await self.db.refresh(row)
        return row

    # ------------------------------------------------------------------ plan management
    async def list_plans(self, *, active_only: bool) -> list[SubscriptionPlan]:
        await self.ensure_defaults()
        stmt = select(SubscriptionPlan)
        if active_only:
            stmt = stmt.where(SubscriptionPlan.is_active.is_(True))
        stmt = stmt.order_by(SubscriptionPlan.display_order.asc(), SubscriptionPlan.tier_rank.asc(), SubscriptionPlan.price_paise.asc())
        return list((await self.db.execute(stmt)).scalars())

    async def get_plan(self, public_id: int) -> SubscriptionPlan:
        await self.ensure_defaults()
        plan = (await self.db.execute(select(SubscriptionPlan).where(SubscriptionPlan.public_id == public_id))).scalar_one_or_none()
        if plan is None:
            raise NotFoundError("Subscription plan not found.", code="PLAN_NOT_FOUND")
        return plan

    def _validate_plan_price(self, price_paise: int, settings_row: PaymentSettings, min_p: int | None, max_p: int | None) -> None:
        if min_p is not None and max_p is not None and max_p < min_p:
            raise BadRequestError("Plan max price must be >= plan min price.", code="INVALID_PRICE_RANGE")
        if price_paise < settings_row.min_amount_paise or price_paise > settings_row.max_amount_paise:
            raise BadRequestError(
                f"Plan price must be within payment range ({settings_row.min_amount_paise // 100} - {settings_row.max_amount_paise // 100} INR).",
                code="PRICE_OUT_OF_RANGE",
            )
        if min_p is not None and price_paise < min_p:
            raise BadRequestError("Plan price cannot be below its minimum range.", code="PRICE_OUT_OF_RANGE")
        if max_p is not None and price_paise > max_p:
            raise BadRequestError("Plan price cannot exceed its maximum range.", code="PRICE_OUT_OF_RANGE")

    async def create_plan(self, payload: dict[str, Any]) -> SubscriptionPlan:
        settings_row = await self.get_payment_settings()
        code = str(payload["code"]).strip().lower()
        existing = (await self.db.execute(select(SubscriptionPlan.id).where(SubscriptionPlan.code == code))).first()
        if existing is not None:
            raise ConflictError(f"A plan with code '{code}' already exists.", code="PLAN_CODE_EXISTS")

        self._validate_plan_price(int(payload["price_paise"]), settings_row, payload.get("min_price_paise"), payload.get("max_price_paise"))
        if payload.get("is_recommended"):
            for other in await self.list_plans(active_only=False):
                other.is_recommended = False

        plan = SubscriptionPlan(
            public_id=new_public_id(),
            code=code,
            name=str(payload["name"]).strip(),
            description=str(payload.get("description") or "").strip(),
            price_paise=int(payload["price_paise"]),
            min_price_paise=payload.get("min_price_paise"),
            max_price_paise=payload.get("max_price_paise"),
            billing_duration_days=int(payload["billing_duration_days"]),
            billing_label=str(payload["billing_label"]).strip(),
            max_courses=payload.get("max_courses"),
            features=list(payload.get("features") or []),
            course_access_rules=dict(payload.get("course_access_rules") or {"all_approved_courses": True, "course_ids": []}),
            assessment_access=dict(payload.get("assessment_access") or {"chapter_tests": True, "module_tests": False, "final_exam": False, "proctoring": False}),
            certificate_level=str(payload.get("certificate_level") or "basic"),
            support_tier=str(payload.get("support_tier") or "Email Support"),
            is_active=bool(payload.get("is_active", True)),
            is_recommended=bool(payload.get("is_recommended", False)),
            display_order=int(payload.get("display_order", 0)),
            tier_rank=int(payload.get("tier_rank", 1)),
        )
        self.db.add(plan)
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def update_plan(self, public_id: int, payload: dict[str, Any]) -> SubscriptionPlan:
        plan = await self.get_plan(public_id)
        settings_row = await self.get_payment_settings()

        clear_max = bool(payload.pop("clear_max_courses", False))
        new_price = int(payload.get("price_paise", plan.price_paise))
        new_min = payload.get("min_price_paise", plan.min_price_paise)
        new_max = payload.get("max_price_paise", plan.max_price_paise)
        self._validate_plan_price(new_price, settings_row, new_min, new_max)

        if payload.get("is_recommended") is True:
            for other in await self.list_plans(active_only=False):
                if other.id != plan.id:
                    other.is_recommended = False

        for field, value in payload.items():
            if field in ("course_access_rules", "assessment_access") and value is not None:
                setattr(plan, field, dict(value))
            else:
                setattr(plan, field, value)
        if clear_max:
            plan.max_courses = None

        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def delete_plan(self, public_id: int) -> None:
        plan = await self.get_plan(public_id)
        has_subs = (await self.db.execute(select(StudentSubscription.id).where(StudentSubscription.plan_id == plan.id).limit(1))).first()
        if has_subs is not None:
            # Preserve financial/audit integrity by deactivating rather than hard deleting plans with purchases
            plan.is_active = False
            plan.is_recommended = False
            await self.db.commit()
            return
        await self.db.delete(plan)
        await self.db.commit()

    # ------------------------------------------------------------------ student subscription status & expiry
    async def expire_due_for_user(self, user_id: int | None = None) -> int:
        now = utcnow()
        stmt = select(StudentSubscription).where(
            StudentSubscription.status == StudentSubStatus.ACTIVE,
            StudentSubscription.ends_at.is_not(None),
            StudentSubscription.ends_at <= now,
        )
        if user_id is not None:
            stmt = stmt.where(StudentSubscription.user_id == user_id)
        due = list((await self.db.execute(stmt)).scalars())
        for sub in due:
            sub.status = StudentSubStatus.EXPIRED
        if due:
            await self.db.commit()
        return len(due)

    async def get_active_subscription(self, user_id: int) -> StudentSubscription | None:
        await self.expire_due_for_user(user_id)
        return (
            await self.db.execute(
                select(StudentSubscription)
                .where(StudentSubscription.user_id == user_id, StudentSubscription.status == StudentSubStatus.ACTIVE)
                .order_by(StudentSubscription.ends_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def courses_for_subscription(self, subscription_id: uuid.UUID) -> list[StudentSubscriptionCourse]:
        return list(
            (
                await self.db.execute(
                    select(StudentSubscriptionCourse)
                    .where(StudentSubscriptionCourse.subscription_id == subscription_id)
                    .order_by(StudentSubscriptionCourse.granted_at.desc())
                )
            ).scalars()
        )

    async def overview_for_student(self, user_id: int) -> dict[str, Any]:
        active = await self.get_active_subscription(user_id)
        history = list(
            (
                await self.db.execute(
                    select(StudentSubscription)
                    .where(StudentSubscription.user_id == user_id)
                    .order_by(StudentSubscription.created_at.desc())
                    .limit(50)
                )
            ).scalars()
        )
        course_map: dict[uuid.UUID, list[StudentSubscriptionCourse]] = {}
        for sub in history:
            course_map[sub.id] = await self.courses_for_subscription(sub.id)

        all_plans = await self.list_plans(active_only=True)
        upgrades: list[SubscriptionPlan] = []
        if active is not None:
            current_plan = await self.db.get(SubscriptionPlan, active.plan_id)
            cur_rank = current_plan.tier_rank if current_plan else 0
            upgrades = [p for p in all_plans if p.tier_rank > cur_rank or (p.id != active.plan_id and p.price_paise > active.price_paise)]
        else:
            upgrades = all_plans

        latest_tx = (
            await self.db.execute(
                select(StudentPaymentTransaction)
                .where(StudentPaymentTransaction.user_id == user_id)
                .order_by(StudentPaymentTransaction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        return {
            "active": active,
            "history": history,
            "course_map": course_map,
            "upgrades": upgrades,
            "latest_tx": latest_tx,
        }

    async def _assert_independent_student(self, auth: AccessTokenClaims) -> None:
        category = await resolve_student_category(self.settings, auth)
        if category != "individual":
            raise PermissionDeniedError(
                "Institution-managed students cannot make direct payments. Submit a payment request to your Institution Head.",
                code="INSTITUTION_STUDENT_DIRECT_PAYMENT_FORBIDDEN",
            )

    # ------------------------------------------------------------------ checkout pricing & creation
    async def compute_checkout_summary(
        self,
        auth: AccessTokenClaims,
        *,
        plan_public_id: int,
        course_id: int | None,
        action_type: str,
    ) -> dict[str, Any]:
        await self._assert_independent_student(auth)
        settings_row = await self.get_payment_settings()
        if not settings_row.payments_enabled:
            raise ConflictError("Online course payments are currently disabled by Administrator.", code="PAYMENTS_DISABLED")

        plan = await self.get_plan(plan_public_id)
        if not plan.is_active:
            raise ConflictError("Selected subscription plan is no longer active.", code="PLAN_INACTIVE")

        course_title: str | None = None
        if course_id is not None:
            info = await verify_course_eligible_for_student(self.settings, auth, course_id)
            course_title = info["title"]
            rules = plan.course_access_rules or {}
            if not rules.get("all_approved_courses", True):
                allowed = {str(cid) for cid in (rules.get("course_ids") or [])}
                if str(course_id) not in allowed:
                    raise PermissionDeniedError(
                        f"Selected course is not included in {plan.name}.",
                        code="COURSE_NOT_IN_PLAN",
                    )

        active = await self.get_active_subscription(auth.user_id)
        original_paise = plan.price_paise
        discount_paise = 0
        discount_note: str | None = None
        current_plan_name: str | None = None

        if action_type == TxActionType.UPGRADE:
            if active is None:
                raise ConflictError("You do not have an active subscription to upgrade from.", code="NO_ACTIVE_SUBSCRIPTION")
            current_plan_name = active.plan_name
            current_plan = await self.db.get(SubscriptionPlan, active.plan_id)
            cur_rank = current_plan.tier_rank if current_plan else 0
            if plan.id == active.plan_id or (plan.tier_rank <= cur_rank and plan.price_paise <= active.price_paise):
                raise ConflictError("Select a higher-tier plan to upgrade.", code="INVALID_UPGRADE_TARGET")
            if settings_row.upgrade_pricing_mode == "price_difference":
                discount_paise = min(active.price_paise, max(0, original_paise - 100))
                discount_note = f"Upgrade credit from {active.plan_name}"
        elif action_type == TxActionType.RENEW:
            if active is not None:
                current_plan_name = active.plan_name

        taxable_paise = max(0, original_paise - discount_paise)
        cgst, sgst, igst = tax.gst(taxable_paise, settings_row.tax_rate_percent, intra_state=True)
        tax_paise = cgst + sgst + igst
        total_paise = taxable_paise + tax_paise

        return {
            "settings_row": settings_row,
            "plan": plan,
            "course_id": course_id,
            "course_title": course_title,
            "action_type": action_type,
            "original_amount_paise": original_paise,
            "discount_paise": discount_paise,
            "discount_note": discount_note,
            "taxable_paise": taxable_paise,
            "tax_paise": tax_paise,
            "tax_rate_percent": settings_row.tax_rate_percent,
            "total_amount_paise": total_paise,
            "current_plan_name": current_plan_name,
        }

    def _validate_method_allowed(self, method: str, accepted_methods: dict[str, bool]) -> None:
        key = _METHOD_TO_SETTING_KEY.get(method)
        if not key or not accepted_methods.get(key, False):
            raise BadRequestError(f"Payment method '{method}' is not enabled by Administrator.", code="PAYMENT_METHOD_DISABLED")

    async def start_checkout(
        self,
        auth: AccessTokenClaims,
        *,
        plan_public_id: int,
        course_id: int | None,
        payment_method: str,
        action_type: str,
        student_name: str | None,
        student_email: str | None,
    ) -> tuple[StudentPaymentTransaction, dict[str, Any]]:
        calc = await self.compute_checkout_summary(
            auth,
            plan_public_id=plan_public_id,
            course_id=course_id,
            action_type=action_type,
        )
        settings_row: PaymentSettings = calc["settings_row"]
        plan: SubscriptionPlan = calc["plan"]
        self._validate_method_allowed(payment_method, settings_row.accepted_methods)

        org_id = auth.organization_id or 0
        now = utcnow()
        tx_public_id = new_public_id()
        sub_public_id = new_public_id()
        tx_ref = f"TXN-{now.strftime('%Y%m%d')}-{str(tx_public_id)[-6:]}"

        # Create pending StudentSubscription record (never active before verification)
        sub = StudentSubscription(
            public_id=sub_public_id,
            user_id=auth.user_id,
            organization_id=org_id,
            plan_id=plan.id,
            plan_code=plan.code,
            plan_name=plan.name,
            price_paise=plan.price_paise,
            duration_days=plan.billing_duration_days,
            max_courses=plan.max_courses,
            features_snapshot=list(plan.features or []),
            assessment_access_snapshot=dict(plan.assessment_access or {}),
            certificate_level=plan.certificate_level,
            status=StudentSubStatus.PENDING,
        )
        self.db.add(sub)
        await self.db.flush()

        # Issue GST-compliant invoice for the student
        invoice: Invoice | None = None
        draft = await self.invoices.create_draft(
            org_id=org_id,
            kind=InvoiceKind.STUDENT_SUBSCRIPTION,
            source_type="student_subscription",
            source_id=str(sub_public_id),
            lines=[
                {
                    "description": f"{plan.name} ({plan.billing_duration_days} days)"
                    + (f" — {calc['course_title']}" if calc["course_title"] else ""),
                    "quantity": 1,
                    "unit_amount": calc["original_amount_paise"],
                }
            ],
            discount=calc["discount_paise"],
            note=calc["discount_note"],
        )
        if draft is not None:
            # Align invoice tax with configured PaymentSettings tax rate when PaymentSettings differs from default
            draft.taxable = calc["taxable_paise"]
            draft.cgst = calc["tax_paise"] // 2
            draft.sgst = calc["tax_paise"] - draft.cgst
            draft.igst = 0
            draft.total = calc["total_amount_paise"]
            today = now.date()
            fy = tax.financial_year(today)
            seq = await self.invoices.next_number(f"INV/{fy}")
            draft.number = f"INV/{fy}/{seq:06d}"
            draft.issue_date = today
            draft.due_date = today + timedelta(days=self.settings.INVOICE_DUE_DAYS)
            draft.status = InvoiceStatus.ISSUED
            draft.customer = {
                "legal_name": (student_name or f"Student {auth.user_id}")[:200],
                "gstin": None,
                "state": self.settings.SELLER_STATE,
                "address": "",
                "email": student_email,
            }
            draft.place_of_supply = self.settings.SELLER_STATE
            invoice = draft
            await self.db.flush()

        # Create order via Razorpay or Test-mode gateway
        total_amount = calc["total_amount_paise"]
        if self.gateway.configured:
            try:
                gw_order = await self.gateway.create_order(
                    amount=total_amount,
                    currency="INR",
                    receipt=tx_ref,
                    notes={
                        "transaction_ref": tx_ref,
                        "plan_code": plan.code,
                        "user_id": str(auth.user_id),
                        "course_id": str(course_id or ""),
                    },
                )
                order_id = gw_order.order_id
                provider = self.settings.PAYMENT_PROVIDER
            except PaymentGatewayNotConfigured as exc:
                raise UpstreamUnavailableError("Online payment gateway is not configured.", code="PAYMENT_GATEWAY_NOT_CONFIGURED") from exc
            except (Unavailable, Rejected) as exc:
                raise UpstreamUnavailableError("Could not start payment order with gateway.", code="PAYMENT_GATEWAY_UNAVAILABLE") from exc
        elif not self.settings.is_production_like:
            order_id = f"order_rzp_test_{secrets.token_hex(8)}"
            provider = "razorpay_test"
        else:
            raise UpstreamUnavailableError("Payment gateway keys are missing.", code="PAYMENT_GATEWAY_NOT_CONFIGURED")

        rupees = f"{total_amount / 100:.2f}"
        upi_qr_payload = (
            f"upi://pay?pa={quote(settings_row.upi_vpa)}&pn={quote(settings_row.upi_merchant_name)}"
            f"&tr={quote(order_id)}&tn={quote(tx_ref)}&am={rupees}&cu=INR"
        )
        expires_at = now + timedelta(minutes=10)

        tx = StudentPaymentTransaction(
            public_id=tx_public_id,
            transaction_ref=tx_ref,
            user_id=auth.user_id,
            payer_user_id=auth.user_id,
            payer_role="student",
            payment_scope=PaymentScope.INDEPENDENT_STUDENT,
            student_count=1,
            organization_id=org_id,
            subscription_id=sub.id,
            plan_id=plan.id,
            plan_code=plan.code,
            plan_name=plan.name,
            course_id=course_id,
            course_title=calc["course_title"],
            action_type=action_type,
            original_amount_paise=calc["original_amount_paise"],
            discount_paise=calc["discount_paise"],
            tax_paise=calc["tax_paise"],
            total_amount_paise=total_amount,
            currency="INR",
            payment_method=payment_method,
            gateway_provider=provider,
            gateway_order_id=order_id,
            upi_qr_payload=upi_qr_payload,
            status=TxStatus.PENDING,
            invoice_id=invoice.id if invoice else None,
            invoice_number=invoice.number if invoice else None,
            expires_at=expires_at,
        )
        self.db.add(tx)
        await self.db.commit()
        await self.db.refresh(tx)

        checkout_payload = {
            "provider": provider,
            "test_mode": self.is_test_mode,
            "key_id": self._checkout_key_id(),
            "order_id": order_id,
            "amount": total_amount,
            "currency": "INR",
            "seller_name": settings_row.upi_merchant_name,
            "upi_qr_payload": upi_qr_payload,
            "expires_at": expires_at,
        }
        return tx, checkout_payload

    # ------------------------------------------------------------------ verification, webhook capture & activation
    async def get_owned_transaction(self, user_id: int, tx_public_id: int) -> StudentPaymentTransaction:
        tx = (
            await self.db.execute(
                select(StudentPaymentTransaction).where(
                    StudentPaymentTransaction.public_id == tx_public_id,
                    (
                        (StudentPaymentTransaction.user_id == user_id)
                        | StudentPaymentTransaction.id.in_(
                            select(StudentPaymentAllocation.transaction_id).where(
                                StudentPaymentAllocation.student_user_id == user_id
                            )
                        )
                    ),
                )
            )
        ).scalar_one_or_none()
        if tx is None:
            raise NotFoundError("Transaction not found.", code="TRANSACTION_NOT_FOUND")
        return tx

    def _signature_matches(self, order_id: str, payment_id: str, signature: str) -> bool:
        expected = sign(f"{order_id}|{payment_id}".encode(), self._checkout_secret())
        return hmac.compare_digest(expected, signature)

    async def verify_student_payment(
        self,
        auth: AccessTokenClaims,
        tx_public_id: int,
        *,
        order_id: str,
        payment_id: str | None,
        signature: str | None,
        outcome: str,
        failure_reason: str | None,
    ) -> tuple[StudentPaymentTransaction, StudentSubscription | None]:
        await self._assert_independent_student(auth)
        tx = await self.get_owned_transaction(auth.user_id, tx_public_id)
        if tx.gateway_order_id != order_id:
            raise BadRequestError("Order ID does not match this transaction.", code="ORDER_MISMATCH")

        if outcome == "pending":
            if tx.status == TxStatus.PENDING:
                tx.status = TxStatus.PROCESSING
                await self.db.commit()
                await self.db.refresh(tx)
            sub = await self.get_active_subscription(auth.user_id)
            return tx, sub

        if outcome == "failed":
            await self.fail_by_order(order_id, reason=failure_reason or "Payment declined by gateway.")
            await self.db.refresh(tx)
            return tx, await self.get_active_subscription(auth.user_id)

        # outcome == "succeeded": cryptographic HMAC signature is mandatory
        if not payment_id or not signature or not self._signature_matches(order_id, payment_id, signature):
            raise BadRequestError(
                "Payment signature verification failed. Subscription was not activated.",
                code="INVALID_SIGNATURE",
            )

        await self.capture_by_order(order_id, payment_id=payment_id, signature=signature, amount=tx.total_amount_paise)
        await self.db.refresh(tx)
        active = await self.get_active_subscription(auth.user_id)
        return tx, active

    async def sign_test_gateway_payment(self, auth: AccessTokenClaims, tx_public_id: int, *, outcome: str, payment_id: str | None, failure_reason: str | None) -> dict[str, Any]:
        """Local/test helper that simulates the Razorpay server sending an authentic HMAC-signed callback."""
        if self.settings.is_production_like:
            raise PermissionDeniedError("Test gateway simulation is disabled in production.", code="DISABLED_IN_PROD")
        await self._assert_independent_student(auth)
        tx = await self.get_owned_transaction(auth.user_id, tx_public_id)
        if outcome == "failed":
            await self.fail_by_order(tx.gateway_order_id, reason=failure_reason or "Payment failed during UPI/Card authorization.")
            return {"status": "failed", "order_id": tx.gateway_order_id}
        pid = payment_id or f"pay_test_{secrets.token_hex(6)}"
        sig = sign(f"{tx.gateway_order_id}|{pid}".encode(), self._checkout_secret())
        result = await self.capture_by_order(tx.gateway_order_id, payment_id=pid, signature=sig, amount=tx.total_amount_paise)
        return {"status": result, "order_id": tx.gateway_order_id, "payment_id": pid, "signature": sig}

    async def capture_by_order(
        self,
        order_id: str,
        *,
        payment_id: str | None,
        signature: str | None = None,
        amount: int | None = None,
    ) -> str:
        """Idempotently capture payment for an order under row lock, activate subscription, and grant course access."""
        tx = (
            await self.db.execute(
                select(StudentPaymentTransaction)
                .where(StudentPaymentTransaction.gateway_order_id == order_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if tx is None:
            return "ignored"
        if tx.status == TxStatus.SUCCEEDED:
            return "ignored"
        if tx.status == TxStatus.FAILED:
            return "rejected"
        if tx.payer_role == "institution_head":
            from app.services.institution_payment_service import InstitutionPaymentService

            await InstitutionPaymentService(self.db, self.settings)._activate_institution_transaction(
                tx,
                payment_id=payment_id or f"pay_wh_{secrets.token_hex(6)}",
                signature=signature,
                paid_by=tx.payer_user_id,
            )
            return "captured"

        if payment_id:
            reused = (
                await self.db.execute(
                    select(StudentPaymentTransaction.id).where(
                        StudentPaymentTransaction.gateway_payment_id == payment_id,
                        StudentPaymentTransaction.id != tx.id,
                    )
                )
            ).first()
            if reused is not None:
                tx.status = TxStatus.FAILED
                tx.failure_reason = "Duplicate gateway payment ID detected."
                await self.db.commit()
                return "rejected"

        if amount is not None and amount != tx.total_amount_paise:
            tx.status = TxStatus.FAILED
            tx.failure_reason = "Captured amount mismatch."
            await self.db.commit()
            return "rejected"

        now = utcnow()
        tx.status = TxStatus.SUCCEEDED
        tx.gateway_payment_id = payment_id
        tx.gateway_signature = signature
        tx.paid_at = now
        tx.failure_reason = None

        if tx.invoice_id:
            inv = await self.db.get(Invoice, tx.invoice_id)
            if inv is not None and inv.status in (InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE):
                inv.amount_paid = inv.total
                inv.status = InvoiceStatus.PAID

        pending_sub = await self.db.get(StudentSubscription, tx.subscription_id)
        assert pending_sub is not None

        # Prevent duplicate active subscriptions: handle renew vs upgrade vs new
        existing_actives = list(
            (
                await self.db.execute(
                    select(StudentSubscription)
                    .where(
                        StudentSubscription.user_id == tx.user_id,
                        StudentSubscription.status == StudentSubStatus.ACTIVE,
                        StudentSubscription.id != pending_sub.id,
                    )
                    .with_for_update()
                )
            ).scalars()
        )

        target_sub: StudentSubscription = pending_sub
        carried_courses: list[tuple[int, str]] = []

        if tx.action_type == TxActionType.RENEW and existing_actives and existing_actives[0].plan_id == pending_sub.plan_id:
            active_sub = existing_actives[0]
            base_end = active_sub.ends_at if active_sub.ends_at and active_sub.ends_at > now else now
            active_sub.ends_at = base_end + timedelta(days=pending_sub.duration_days)
            pending_sub.status = StudentSubStatus.SUPERSEDED
            pending_sub.replaced_subscription_id = active_sub.id
            tx.subscription_id = active_sub.id
            target_sub = active_sub
        else:
            for prev in existing_actives:
                prev_courses = await self.courses_for_subscription(prev.id)
                for pc in prev_courses:
                    carried_courses.append((pc.course_id, pc.course_title))
                prev.status = StudentSubStatus.SUPERSEDED
                pending_sub.replaced_subscription_id = prev.id

            pending_sub.status = StudentSubStatus.ACTIVE
            pending_sub.starts_at = now
            pending_sub.ends_at = now + timedelta(days=pending_sub.duration_days)
            target_sub = pending_sub

        # Grant carried-over courses + newly chosen course respecting max_courses limit
        existing_sub_courses = {c.course_id for c in await self.courses_for_subscription(target_sub.id)}
        to_grant: list[tuple[int, str]] = []
        for cid, ctitle in carried_courses:
            if cid not in existing_sub_courses and all(g[0] != cid for g in to_grant):
                to_grant.append((cid, ctitle))
        if tx.course_id and tx.course_id not in existing_sub_courses and all(g[0] != tx.course_id for g in to_grant):
            to_grant.append((tx.course_id, tx.course_title or f"Course {tx.course_id}"))

        granted_courses: list[tuple[int, str]] = []
        for cid, ctitle in to_grant:
            current_total = len(existing_sub_courses) + len(granted_courses)
            if target_sub.max_courses is not None and current_total >= target_sub.max_courses:
                break
            self.db.add(
                StudentSubscriptionCourse(
                    subscription_id=target_sub.id,
                    user_id=tx.user_id,
                    course_id=cid,
                    course_title=ctitle[:200],
                    granted_at=now,
                )
            )
            granted_courses.append((cid, ctitle))

        write_event(
            self.db,
            event_type="student_subscription.activated",
            aggregate_type="student_subscription",
            aggregate_id=target_sub.id,
            payload={
                "subscription_id": str(target_sub.public_id),
                "user_id": str(target_sub.user_id),
                "organization_id": str(target_sub.organization_id),
                "plan_code": target_sub.plan_code,
                "plan_name": target_sub.plan_name,
                "starts_at": _iso(target_sub.starts_at),
                "ends_at": _iso(target_sub.ends_at),
                "transaction_ref": tx.transaction_ref,
                "occurred_at": _iso(now),
            },
        )
        await self.db.commit()

        # Sync course_access & learning enrollments immediately across services
        assert target_sub.starts_at is not None and target_sub.ends_at is not None
        for cid, ctitle in granted_courses:
            await sync_student_course_enrollment(
                self.settings,
                user_id=tx.user_id,
                organization_id=tx.organization_id,
                course_id=cid,
                course_title=ctitle,
                starts_at=target_sub.starts_at,
                ends_at=target_sub.ends_at,
            )

        return "paid"

    async def fail_by_order(self, order_id: str, *, reason: str) -> str:
        tx = (
            await self.db.execute(
                select(StudentPaymentTransaction)
                .where(StudentPaymentTransaction.gateway_order_id == order_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if tx is None or tx.status not in (TxStatus.PENDING, TxStatus.PROCESSING):
            return "ignored"
        if tx.payer_role == "institution_head":
            from app.services.institution_payment_service import InstitutionPaymentService

            await InstitutionPaymentService(self.db, self.settings)._fail_institution_transaction(tx, reason)
            return "failed"
        tx.status = TxStatus.FAILED
        tx.failure_reason = reason[:300]
        sub = await self.db.get(StudentSubscription, tx.subscription_id)
        if sub is not None and sub.status == StudentSubStatus.PENDING:
            sub.status = StudentSubStatus.FAILED
        await self.db.commit()
        return "failed"

    # ------------------------------------------------------------------ enroll another course within active plan limit
    async def enroll_course_under_plan(self, auth: AccessTokenClaims, course_id: int) -> StudentSubscription:
        active = await self.get_active_subscription(auth.user_id)
        if active is None:
            raise PermissionDeniedError("An active subscription is required to access this course.", code="SUBSCRIPTION_REQUIRED")

        info = await verify_course_eligible_for_student(self.settings, auth, course_id)
        plan = await self.db.get(SubscriptionPlan, active.plan_id)
        if plan:
            rules = plan.course_access_rules or {}
            if not rules.get("all_approved_courses", True):
                allowed = {str(cid) for cid in (rules.get("course_ids") or [])}
                if str(course_id) not in allowed:
                    raise PermissionDeniedError(f"This course is not included in your {active.plan_name}.", code="COURSE_NOT_IN_PLAN")

        existing = await self.courses_for_subscription(active.id)
        if any(c.course_id == course_id for c in existing):
            return active

        if active.max_courses is not None and len(existing) >= active.max_courses:
            raise PermissionDeniedError(
                f"Course limit reached ({len(existing)}/{active.max_courses} courses on {active.plan_name}). Upgrade your plan to unlock more courses.",
                code="PLAN_LIMIT_REACHED",
            )

        now = utcnow()
        self.db.add(
            StudentSubscriptionCourse(
                subscription_id=active.id,
                user_id=auth.user_id,
                course_id=course_id,
                course_title=info["title"][:200],
                granted_at=now,
            )
        )
        await self.db.commit()

        assert active.starts_at is not None and active.ends_at is not None
        await sync_student_course_enrollment(
            self.settings,
            user_id=auth.user_id,
            organization_id=auth.organization_id or 0,
            course_id=course_id,
            course_title=info["title"],
            starts_at=active.starts_at,
            ends_at=active.ends_at,
        )
        return active

    # ------------------------------------------------------------------ payment history & admin reports
    async def list_transactions(
        self,
        *,
        user_id: int | None = None,
        status: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[StudentPaymentTransaction], int]:
        stmt = select(StudentPaymentTransaction)
        if user_id is not None:
            stmt = stmt.where(
                (StudentPaymentTransaction.user_id == user_id)
                | StudentPaymentTransaction.id.in_(
                    select(StudentPaymentAllocation.transaction_id).where(
                        StudentPaymentAllocation.student_user_id == user_id
                    )
                )
            )
        if status:
            stmt = stmt.where(StudentPaymentTransaction.status == status)
        if from_date:
            stmt = stmt.where(StudentPaymentTransaction.created_at >= from_date)
        if to_date:
            stmt = stmt.where(StudentPaymentTransaction.created_at <= to_date)
        if search and search.strip():
            term = f"%{search.strip()}%"
            stmt = stmt.where(
                StudentPaymentTransaction.transaction_ref.ilike(term)
                | StudentPaymentTransaction.plan_name.ilike(term)
                | StudentPaymentTransaction.course_title.ilike(term)
            )
        total = int((await self.db.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))).scalar_one())
        rows = list(
            (
                await self.db.execute(
                    stmt.order_by(desc(StudentPaymentTransaction.created_at))
                    .limit(per_page)
                    .offset((page - 1) * per_page)
                )
            ).scalars()
        )
        return rows, total

    async def admin_payment_reports(self) -> dict[str, Any]:
        await self.expire_due_for_user(None)
        rev = int(
            (
                await self.db.execute(
                    select(func.coalesce(func.sum(StudentPaymentTransaction.total_amount_paise), 0)).where(
                        StudentPaymentTransaction.status == TxStatus.SUCCEEDED
                    )
                )
            ).scalar_one()
        )
        succeeded_count = int(
            (await self.db.execute(select(func.count()).select_from(StudentPaymentTransaction).where(StudentPaymentTransaction.status == TxStatus.SUCCEEDED))).scalar_one()
        )
        pending_count = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(StudentPaymentTransaction).where(
                        StudentPaymentTransaction.status.in_([TxStatus.PENDING, TxStatus.PROCESSING])
                    )
                )
            ).scalar_one()
        )
        failed_count = int(
            (await self.db.execute(select(func.count()).select_from(StudentPaymentTransaction).where(StudentPaymentTransaction.status == TxStatus.FAILED))).scalar_one()
        )
        active_subs = int(
            (await self.db.execute(select(func.count()).select_from(StudentSubscription).where(StudentSubscription.status == StudentSubStatus.ACTIVE))).scalar_one()
        )
        breakdown_rows = (
            await self.db.execute(
                select(
                    StudentPaymentTransaction.plan_code,
                    StudentPaymentTransaction.plan_name,
                    func.count(StudentPaymentTransaction.id),
                    func.coalesce(func.sum(StudentPaymentTransaction.total_amount_paise), 0),
                )
                .where(StudentPaymentTransaction.status == TxStatus.SUCCEEDED)
                .group_by(StudentPaymentTransaction.plan_code, StudentPaymentTransaction.plan_name)
            )
        ).all()
        independent_rev = int(
            (
                await self.db.execute(
                    select(func.coalesce(func.sum(StudentPaymentTransaction.total_amount_paise), 0)).where(
                        StudentPaymentTransaction.status == TxStatus.SUCCEEDED,
                        StudentPaymentTransaction.payment_scope == PaymentScope.INDEPENDENT_STUDENT,
                    )
                )
            ).scalar_one()
        )
        institution_rev = int(
            (
                await self.db.execute(
                    select(func.coalesce(func.sum(StudentPaymentTransaction.total_amount_paise), 0)).where(
                        StudentPaymentTransaction.status == TxStatus.SUCCEEDED,
                        StudentPaymentTransaction.payment_scope.in_([PaymentScope.INSTITUTION_SINGLE, PaymentScope.INSTITUTION_BULK]),
                    )
                )
            ).scalar_one()
        )
        pending_requests_count = int(
            (
                await self.db.execute(
                    select(func.count()).select_from(StudentPaymentRequest).where(
                        StudentPaymentRequest.status.in_([PaymentRequestStatus.PENDING, PaymentRequestStatus.APPROVED])
                    )
                )
            ).scalar_one()
        )
        inst_rows = (
            await self.db.execute(
                select(
                    StudentPaymentTransaction.organization_id,
                    func.count(StudentPaymentTransaction.id),
                    func.coalesce(func.sum(StudentPaymentTransaction.student_count), 0),
                    func.coalesce(func.sum(StudentPaymentTransaction.total_amount_paise), 0),
                )
                .where(
                    StudentPaymentTransaction.status == TxStatus.SUCCEEDED,
                    StudentPaymentTransaction.payment_scope.in_([PaymentScope.INSTITUTION_SINGLE, PaymentScope.INSTITUTION_BULK]),
                )
                .group_by(StudentPaymentTransaction.organization_id)
            )
        ).all()
        org_names = await fetch_institution_names(self.settings, [int(r[0]) for r in inst_rows if r[0]])
        course_rows = (
            await self.db.execute(
                select(
                    StudentPaymentTransaction.course_id,
                    StudentPaymentTransaction.course_title,
                    func.count(StudentPaymentTransaction.id),
                    func.coalesce(func.sum(StudentPaymentTransaction.total_amount_paise), 0),
                )
                .where(
                    StudentPaymentTransaction.status == TxStatus.SUCCEEDED,
                    StudentPaymentTransaction.course_id.is_not(None),
                )
                .group_by(StudentPaymentTransaction.course_id, StudentPaymentTransaction.course_title)
            )
        ).all()
        plan_breakdown = [
            {"plan_code": r[0], "plan_name": r[1], "transactions": int(r[2]), "revenue_paise": int(r[3])}
            for r in breakdown_rows
        ]
        return {
            "total_revenue_paise": rev,
            "independent_revenue_paise": independent_rev,
            "institution_revenue_paise": institution_rev,
            "succeeded_count": succeeded_count,
            "pending_count": pending_count,
            "failed_count": failed_count,
            "pending_requests_count": pending_requests_count,
            "active_subscriptions_count": active_subs,
            "plan_breakdown": plan_breakdown,
            "plan_revenue": plan_breakdown,
            "institution_revenue": [
                {
                    "organization_id": str(r[0]),
                    "organization_name": org_names.get(int(r[0]), f"Institution {r[0]}"),
                    "transactions": int(r[1]),
                    "students_covered": int(r[2]),
                    "revenue_paise": int(r[3]),
                }
                for r in inst_rows
            ],
            "course_revenue": [
                {
                    "course_id": str(r[0]),
                    "course_title": r[1] or f"Course {r[0]}",
                    "transactions": int(r[2]),
                    "revenue_paise": int(r[3]),
                }
                for r in course_rows
            ],
        }
