"""End-to-end backend verification tests for Student Subscription Plans, Payment Settings, Checkout, Signature/Webhook Verification, Upgrades, Expiry & Access Control."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import unittest
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient
from lms_common.auth import AccessTokenClaims

from app.api.deps import _authenticate
from app.core.config import Settings, get_settings
from app.core.time import utcnow
from app.db.session import build_engine, build_sessionmaker
from app.main import create_app
from app.models import Base
from app.models.student_subscription import StudentSubscription
from sqlalchemy import select

API = "/api/v1"
ADMIN_ID = 1755000000900001
STUDENT_ID = 1755000000900002
INST_ID = 1755000000900101
COURSE_1 = 1755000000901001
COURSE_2 = 1755000000901002
WEBHOOK_SECRET = "test-webhook-secret"


def _claims(user_id: int, role: str, scopes: tuple[str, ...] = ()) -> AccessTokenClaims:
    return AccessTokenClaims(
        user_id=user_id,
        organization_id=INST_ID if role == "student" else None,
        organization_type="institution" if role == "student" else None,
        role=role,
        scopes=frozenset(scopes),
        session_id="sess-test-1",
        token_id="tok-test-1",
        token_version=1,
        issued_at=1700000000,
        expires_at=1900000000,
    )


class StudentSubscriptionsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.current_auth = _claims(ADMIN_ID, "super_admin", ("billing.manage",))
        self.settings = Settings(
            ENVIRONMENT="test",
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            REDIS_URL="redis://localhost:6379/15",
            DOCS_ENABLED=False,
            RATE_LIMIT_ENABLED=False,
            LOG_JSON=False,
            SELLER_STATE="Karnataka",
            GST_RATE_PERCENT=0,
            PAYMENT_PROVIDER="generic",
            PAYMENT_GATEWAY_URL="http://pay.test",
            PAYMENT_WEBHOOK_SECRET=WEBHOOK_SECRET,
        )

    async def _setup_client(self):
        engine = build_engine(self.settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        app = create_app(self.settings)
        app.state.engine = engine
        app.state.sessionmaker = build_sessionmaker(engine)
        app.state.redis = fakeredis.aioredis.FakeRedis()
        app.dependency_overrides[get_settings] = lambda: self.settings
        app.dependency_overrides[_authenticate] = lambda: self.current_auth
        client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        return engine, app, client

    def test_full_student_subscription_and_payment_lifecycle(self) -> None:
        asyncio.run(self._run_lifecycle())

    async def _run_lifecycle(self) -> None:
        engine, app, client = await self._setup_client()
        from app.gateways.payment import GatewayOrder
        mock_order = AsyncMock(
            side_effect=lambda amount, currency="INR", receipt="", notes=None: GatewayOrder(
                order_id=f"order_test_{receipt}", amount=amount, currency=currency
            )
        )
        mock_eligible = AsyncMock(
            side_effect=lambda _s, _a, cid: {"course_id": cid, "title": f"Python Bootcamp {cid}", "version_id": 999}
        )
        mock_sync = AsyncMock(return_value=True)

        with (
            patch("app.gateways.payment.PaymentGateway.create_order", mock_order),
            patch("app.services.student_subscription_service.verify_course_eligible_for_student", mock_eligible),
            patch("app.services.student_subscription_service.sync_student_course_enrollment", mock_sync),
        ):
            try:
                # 1. Seeded plans visible & Admin CRUD + Payment Settings work
                self.current_auth = _claims(ADMIN_ID, "super_admin", ("billing.manage",))
                r = await client.get(f"{API}/admin/subscription-plans")
                self.assertEqual(r.status_code, 200)
                plans = r.json()["plans"]
                self.assertEqual([p["code"] for p in plans], ["base", "silver", "gold"])
                silver = next(p for p in plans if p["code"] == "silver")
                base = next(p for p in plans if p["code"] == "base")
                gold = next(p for p in plans if p["code"] == "gold")
                self.assertTrue(silver["is_recommended"])

                # Update Admin plan price & verify student reflects change (Scenario 15)
                r = await client.patch(
                    f"{API}/admin/subscription-plans/{base['plan_id']}",
                    json={"price_paise": 54900},
                )
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json()["plan"]["price_paise"], 54900)

                # Update payment settings: tax=0, disable payments briefly (Scenario 16)
                r = await client.put(
                    f"{API}/admin/payment-settings",
                    json={
                        "payments_enabled": False,
                        "min_amount_paise": 49900,
                        "max_amount_paise": 499900,
                        "accepted_methods": {"razorpay": True, "stripe": False, "upi": True, "cards": True, "netbanking": False, "wallet": True},
                        "tax_rate_percent": 0,
                        "upgrade_pricing_mode": "price_difference",
                        "upi_vpa": "examlms@icici",
                        "upi_merchant_name": "ExamLMS",
                    },
                )
                self.assertEqual(r.status_code, 200)

                # Student checkout blocked when payments_enabled=False
                self.current_auth = _claims(STUDENT_ID, "student", ("store.buy", "learning.study"))
                r = await client.post(
                    f"{API}/student/checkout",
                    json={"plan_id": silver["plan_id"], "course_id": str(COURSE_1), "payment_method": "upi"},
                )
                self.assertEqual(r.status_code, 409)

                # Re-enable payments & test disabled method rejection
                self.current_auth = _claims(ADMIN_ID, "super_admin", ("billing.manage",))
                await client.put(
                    f"{API}/admin/payment-settings",
                    json={
                        "payments_enabled": True,
                        "min_amount_paise": 49900,
                        "max_amount_paise": 499900,
                        "accepted_methods": {"razorpay": True, "stripe": False, "upi": True, "cards": True, "netbanking": False, "wallet": True},
                        "tax_rate_percent": 0,
                        "upgrade_pricing_mode": "price_difference",
                        "upi_vpa": "examlms@icici",
                        "upi_merchant_name": "ExamLMS",
                    },
                )

                self.current_auth = _claims(STUDENT_ID, "student", ("store.buy", "learning.study"))
                r = await client.post(
                    f"{API}/student/checkout",
                    json={"plan_id": silver["plan_id"], "course_id": str(COURSE_1), "payment_method": "netbanking"},
                )
                self.assertEqual(r.status_code, 400)

                # 2. Failed payment must NOT activate subscription (Scenario 7)
                r = await client.post(
                    f"{API}/student/checkout",
                    json={"plan_id": base["plan_id"], "course_id": str(COURSE_1), "payment_method": "card"},
                )
                self.assertEqual(r.status_code, 201)
                tx_fail = r.json()["transaction"]
                r = await client.post(
                    f"{API}/student/payments/{tx_fail['tx_id']}/verify",
                    json={"razorpay_order_id": tx_fail["gateway_order_id"], "outcome": "failed", "failure_reason": "Card declined"},
                )
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json()["transaction"]["status"], "failed")
                self.assertIsNone(r.json()["subscription"])

                # 3. Forged signature rejected & does not activate (Scenario 5 / Security)
                r = await client.post(
                    f"{API}/student/checkout",
                    json={"plan_id": base["plan_id"], "course_id": str(COURSE_1), "payment_method": "upi"},
                )
                self.assertEqual(r.status_code, 201)
                tx_upi = r.json()["transaction"]
                checkout_info = r.json()["checkout"]
                self.assertTrue(checkout_info["upi_qr_payload"].startswith("upi://pay?pa="))

                r = await client.post(
                    f"{API}/student/payments/{tx_upi['tx_id']}/verify",
                    json={
                        "razorpay_order_id": tx_upi["gateway_order_id"],
                        "razorpay_payment_id": "pay_fake_1",
                        "razorpay_signature": "forged_signature",
                        "outcome": "succeeded",
                    },
                )
                self.assertEqual(r.status_code, 400)

                # Still not active!
                ov = (await client.get(f"{API}/student/subscription")).json()
                self.assertIsNone(ov["active_subscription"])

                # 4. Signed webhook activates subscription & duplicate webhook is idempotent (Scenario 6 / 17)
                payload_bytes = json.dumps(
                    {
                        "event": "payment.captured",
                        "event_id": "evt_stu_001",
                        "order_id": tx_upi["gateway_order_id"],
                        "payment_id": "pay_wh_001",
                        "amount": tx_upi["total_amount_paise"],
                    }
                ).encode()
                wh_sig = hmac.new(WEBHOOK_SECRET.encode(), payload_bytes, hashlib.sha256).hexdigest()
                r = await client.post(f"{API}/webhooks/payment", content=payload_bytes, headers={"X-Signature": wh_sig})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.json()["result"], "paid")
                self.assertGreaterEqual(mock_sync.call_count, 1)

                # Duplicate webhook delivery returns duplicate without error
                r2 = await client.post(f"{API}/webhooks/payment", content=payload_bytes, headers={"X-Signature": wh_sig})
                self.assertEqual(r2.status_code, 200)
                self.assertEqual(r2.json()["result"], "duplicate")

                ov = (await client.get(f"{API}/student/subscription")).json()
                self.assertIsNotNone(ov["active_subscription"])
                self.assertEqual(ov["active_subscription"]["plan_code"], "base")

                # 5. Upgrade Base -> Silver via price_difference & prevent duplicate active subs (Scenario 9)
                prev = await client.post(
                    f"{API}/student/checkout/preview",
                    json={"plan_id": silver["plan_id"], "action_type": "upgrade"},
                )
                self.assertEqual(prev.status_code, 200)
                summary = prev.json()["summary"]
                # Base updated to 54900, Silver = 99900 -> difference = 45000 paise
                self.assertEqual(summary["discount_paise"], 54900)
                self.assertEqual(summary["total_amount_paise"], 45000)

                co_up = (
                    await client.post(
                        f"{API}/student/checkout",
                        json={"plan_id": silver["plan_id"], "action_type": "upgrade", "payment_method": "razorpay"},
                    )
                ).json()["transaction"]
                cb_up = await client.post(
                    f"{API}/student/payments/{co_up['tx_id']}/test-callback",
                    json={"outcome": "captured"},
                )
                self.assertEqual(cb_up.status_code, 200)
                self.assertEqual(cb_up.json()["subscription"]["plan_code"], "silver")

                # Verify ONLY ONE active subscription exists
                async with app.state.sessionmaker() as check_db:
                    active_rows = list(
                        (await check_db.execute(select(StudentSubscription).where(StudentSubscription.status == "active"))).scalars()
                    )
                    self.assertEqual(len(active_rows), 1)
                    self.assertEqual(active_rows[0].plan_code, "silver")

                # 6. Unlock second course under Silver quota & inspect history filters (Scenario 10)
                enr2 = await client.post(f"{API}/student/subscription/enroll-course", json={"course_id": str(COURSE_2)})
                self.assertEqual(enr2.status_code, 200)
                self.assertEqual(len(enr2.json()["active_subscription"]["courses"]), 2)

                hist = (await client.get(f"{API}/student/payments?status=succeeded")).json()
                self.assertEqual(len(hist["transactions"]), 2)

                # 7. Expired subscription automatically marks expired & stops access (Scenario 12)
                async with app.state.sessionmaker() as check_db:
                    sub = (await check_db.execute(select(StudentSubscription).where(StudentSubscription.status == "active"))).scalar_one()
                    sub.ends_at = utcnow() - timedelta(minutes=5)
                    await check_db.commit()

                ov_after = (await client.get(f"{API}/student/subscription")).json()
                self.assertIsNone(ov_after["active_subscription"])
                self.assertTrue(any(s["status"] == "expired" for s in ov_after["history"]))

                # Admin reports reflect revenue accurately (Scenario 15)
                self.current_auth = _claims(ADMIN_ID, "super_admin", ("billing.manage",))
                rep = (await client.get(f"{API}/admin/payment-reports")).json()
                self.assertEqual(rep["succeeded_count"], 2)
                self.assertEqual(rep["failed_count"], 1)
                self.assertEqual(rep["total_revenue_paise"], 54900 + 45000)

                # Create custom plan (Gold already seeded)
                custom = await client.post(
                    f"{API}/admin/subscription-plans",
                    json={
                        "code": "pro_annual",
                        "name": "Pro Annual",
                        "description": "Yearly access",
                        "price_paise": 499900,
                        "billing_duration_days": 365,
                        "billing_label": "year",
                        "max_courses": None,
                        "features": ["All Courses", "Final Exam"],
                        "assessment_access": {"chapter_tests": True, "module_tests": True, "final_exam": True, "proctoring": True},
                        "certificate_level": "pro",
                        "is_active": True,
                        "is_recommended": False,
                        "tier_rank": 4,
                    },
                )
                self.assertEqual(custom.status_code, 201)
                self.assertEqual(gold["certificate_level"], "pro")
            finally:
                await client.aclose()
                await app.state.redis.aclose()
                await engine.dispose()
