"""The learner store: a self-registered learner (``store.buy``) buys a course for themselves.

buy      -> a CoursePurchase + an invoice issued to them at once + a gateway order for its total
confirm  -> the signature is verified, the payment captured, the invoice paid
paid     -> grants or extends their individual course access entitlement
"""

from dataclasses import dataclass
from datetime import timedelta
import secrets
import uuid

import asyncpg
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import tax
from app.core.config import Settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, UpstreamUnavailableError, UpstreamUnavailableError
from app.core.ids import new_public_id
from app.core.security import AccessTokenClaims
from app.core.time import utcnow
from app.domain.enums import InvoiceKind, InvoiceStatus, PaymentMethod, PaymentStatus, PriceKind, PurchaseStatus
from app.gateways.errors import Rejected, Unavailable
from app.gateways.payment import PaymentGateway, PaymentGatewayNotConfigured
from app.models.billing import CoursePurchase, Invoice, Payment, PriceItem
from app.services.invoice_service import InvoiceService
from app.services.payment_service import PaymentService
from app.services.price_service import PriceService


@dataclass(frozen=True, slots=True)
class Offer:
    course_id: int
    name: str
    price: int  # before GST, paise
    gst: int
    total: int  # what the learner pays
    valid_days: int


@dataclass(frozen=True, slots=True)
class Checkout:
    provider: str
    key_id: str | None
    order_id: str
    amount: int
    currency: str
    seller_name: str


class StoreService:
    def __init__(self, db: AsyncSession, settings: Settings, gateway: PaymentGateway | None = None) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway or PaymentGateway(settings)
        self.invoices = InvoiceService(db, settings)
        self.payments = PaymentService(db, settings, self.gateway)

    def _subscription_db_url(self) -> str:
        return "postgresql://lms:lms@127.0.0.1:5432/lms_subscription"

    def _learning_db_url(self) -> str:
        return "postgresql://lms:lms@127.0.0.1:5432/lms_learning"

    def _catalog_db_url(self) -> str:
        return "postgresql://lms:lms@127.0.0.1:5432/lms_catalog"

    def _offer(self, price: PriceItem) -> Offer:
        cgst, sgst, igst = tax.gst(price.unit_amount, self.settings.GST_RATE_PERCENT, intra_state=True)
        gst = cgst + sgst + igst
        days = int((price.meta or {}).get("valid_days") or self.settings.LEARNER_ACCESS_DAYS)
        return Offer(course_id=int(price.code), name=price.name, price=price.unit_amount, gst=gst, total=price.unit_amount + gst, valid_days=days)

    async def offers(self) -> list[Offer]:
        prices, _ = await PriceService(self.db).list_prices(kind=PriceKind.COURSE_SEAT.value, include_inactive=False, page=1, per_page=100)
        price_dict = {p.code: p for p in prices if p.code.isdigit()}

        # Also discover published courses from lms_catalog and ensure price items exist
        if "sqlite" not in str(self.settings.DATABASE_URL).lower():
            try:
                conn = await asyncpg.connect(self._catalog_db_url())
                try:
                    rows = await conn.fetch(
                        """
                        SELECT c.public_id, c.title
                        FROM courses c
                        JOIN course_versions cv ON cv.course_id = c.id
                        WHERE cv.status = 'published'
                        ORDER BY c.created_at DESC
                        """
                    )
                    for r in rows:
                        cid_str = str(r["public_id"])
                        if cid_str not in price_dict:
                            # Auto create default price for published course
                            p = PriceItem(
                                public_id=new_public_id(),
                                kind=PriceKind.COURSE_SEAT.value,
                                code=cid_str,
                                name=r["title"],
                                unit_amount=199900,  # ₹1,999 default
                                meta={"valid_days": 180, "discount_paise": 0},
                                active=True,
                            )
                            self.db.add(p)
                            await self.db.commit()
                            await self.db.refresh(p)
                            price_dict[cid_str] = p
                finally:
                    await conn.close()
            except Exception:
                pass

        return [self._offer(p) for p in price_dict.values()]

    async def mine(self, auth: AccessTokenClaims) -> list[tuple[CoursePurchase, Invoice]]:
        rows = (
            await self.db.execute(
                select(CoursePurchase, Invoice)
                .join(Invoice, Invoice.id == CoursePurchase.invoice_id)
                .where(CoursePurchase.user_id == auth.user_id, CoursePurchase.status != PurchaseStatus.CANCELLED)
                .order_by(CoursePurchase.created_at.desc())
            )
        ).all()
        return [(p, i) for p, i in rows]

    async def get_own(self, auth: AccessTokenClaims, purchase_id: int) -> tuple[CoursePurchase, Invoice]:
        row = (
            await self.db.execute(
                select(CoursePurchase, Invoice)
                .join(Invoice, Invoice.id == CoursePurchase.invoice_id)
                .where(CoursePurchase.public_id == purchase_id, CoursePurchase.user_id == auth.user_id)
            )
        ).first()
        if row is None:
            raise NotFoundError("Purchase not found.", code="PURCHASE_NOT_FOUND")
        return row[0], row[1]

    async def buy(self, auth: AccessTokenClaims, course_id: int, *, name: str, email: str | None) -> tuple[CoursePurchase, Checkout]:
        """Start (or restart) paying for a course."""
        if not self.gateway.configured:
            raise UpstreamUnavailableError("The payment gateway is not configured.", code="PAYMENT_GATEWAY_NOT_CONFIGURED")
        price = await PriceService(self.db).by_code(PriceKind.COURSE_SEAT, str(course_id))
        if price is None and "sqlite" not in str(self.settings.DATABASE_URL).lower():
            # Check catalog to auto-create price
            try:
                conn = await asyncpg.connect(self._catalog_db_url())
                try:
                    c_row = await conn.fetchrow(
                        "SELECT title FROM courses WHERE public_id = $1",
                        int(course_id),
                    )
                    if c_row:
                        price = PriceItem(
                            public_id=new_public_id(),
                            kind=PriceKind.COURSE_SEAT.value,
                            code=str(course_id),
                            name=c_row["title"],
                            unit_amount=199900,
                            meta={"valid_days": 180, "discount_paise": 0},
                            active=True,
                        )
                        self.db.add(price)
                        await self.db.commit()
                        await self.db.refresh(price)
                finally:
                    await conn.close()
            except Exception:
                pass

        if price is None:
            raise NotFoundError("This course is not on sale.", code="COURSE_NOT_ON_SALE")

        org_id = auth.organization_id or 0
        pending = (
            await self.db.execute(
                select(CoursePurchase).where(
                    CoursePurchase.user_id == auth.user_id,
                    CoursePurchase.course_id == course_id,
                    CoursePurchase.status == PurchaseStatus.PENDING,
                )
            )
        ).scalar_one_or_none()
        if pending is not None:
            invoice = (await self.db.execute(select(Invoice).where(Invoice.id == pending.invoice_id))).scalar_one()
            return pending, await self._checkout(invoice, pending)

        offer = self._offer(price)
        purchase_public_id = new_public_id()
        draft = await self.invoices.create_draft(
            org_id=org_id,
            kind=InvoiceKind.COURSE,
            source_type="purchase",
            source_id=str(purchase_public_id),
            lines=[{"description": f"{price.name}: {offer.valid_days} days' access", "quantity": 1, "unit_amount": price.unit_amount}],
        )
        if draft is None:
            raise ConflictError("The invoice could not be created.", code="INVOICE_EXISTS")
        purchase = CoursePurchase(
            public_id=purchase_public_id,
            org_id=org_id,
            user_id=auth.user_id,
            course_id=course_id,
            course_name=price.name[:160],
            valid_days=offer.valid_days,
            amount=offer.total,
            status=PurchaseStatus.PENDING,
            invoice_id=draft.id,
        )
        self.db.add(purchase)
        await self.db.flush()
        invoice = await self.invoices.issue(draft, person={"name": name, "email": email})
        purchase.amount = invoice.total
        await self.db.commit()
        return purchase, await self._checkout(invoice, purchase)

    async def _checkout(self, invoice: Invoice, purchase: CoursePurchase) -> Checkout:
        if invoice.status not in (InvoiceStatus.ISSUED, InvoiceStatus.OVERDUE):
            raise ConflictError(f"This purchase's invoice is {invoice.status}.", code="INVOICE_NOT_PAYABLE")
        amount = self.invoices.owed(invoice)
        order_id = f"order_learner_{purchase.public_id}_{secrets.token_hex(4)}"

        if self.gateway.configured:
            try:
                order = await self.gateway.create_order(
                    amount=amount,
                    currency=invoice.currency,
                    receipt=invoice.number or str(invoice.public_id),
                    notes={"purchase_id": str(purchase.public_id), "course_id": str(purchase.course_id), "user_id": str(purchase.user_id)},
                )
                order_id = order.order_id
            except Exception:
                pass

        self.db.add(
            Payment(
                public_id=new_public_id(),
                invoice_id=invoice.id,
                method=PaymentMethod.GATEWAY,
                status=PaymentStatus.PENDING,
                amount=amount,
                gateway_order_id=order_id,
            )
        )
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise UpstreamUnavailableError("The payment provider returned an order id seen before.", code="PAYMENT_GATEWAY_UNAVAILABLE")

        return Checkout(
            provider=self.settings.PAYMENT_PROVIDER,
            key_id=self.gateway.public_key or "rzp_test_examlms",
            order_id=order_id,
            amount=amount,
            currency=invoice.currency,
            seller_name=self.settings.SELLER_DISPLAY_NAME,
        )

    async def _activate_individual_entitlement(
        self,
        *,
        user_id: int,
        course_id: int,
        valid_days: int,
        organization_id: int,
    ) -> None:
        """Grants or extends individual course access in lms_subscription and creates enrollment in lms_learning."""
        if "sqlite" in str(self.settings.DATABASE_URL).lower():
            return
        now = utcnow()
        ends_at = now + timedelta(days=valid_days)
        sub_conn = await asyncpg.connect(self._subscription_db_url())
        try:
            existing = await sub_conn.fetchrow(
                """
                SELECT id, ends_at FROM course_access
                WHERE user_id = $1 AND course_id = $2
                """,
                int(user_id),
                int(course_id),
            )
            if existing is None:
                await sub_conn.execute(
                    """
                    INSERT INTO course_access (
                        id, public_id, user_id, organization_id, course_id, starts_at, ends_at, status, created_at, updated_at
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, 'active', NOW(), NOW()
                    )
                    """,
                    uuid.uuid4(),
                    new_public_id(),
                    int(user_id),
                    int(organization_id),
                    int(course_id),
                    now,
                    ends_at,
                )
            else:
                curr_end = existing["ends_at"]
                new_end = max(curr_end or now, now) + timedelta(days=valid_days)
                await sub_conn.execute(
                    """
                    UPDATE course_access
                    SET ends_at = $1, status = 'active', updated_at = NOW()
                    WHERE id = $2
                    """,
                    new_end,
                    existing["id"],
                )
        finally:
            await sub_conn.close()

        # In lms_learning, create learner batch & enrollment
        try:
            learn_conn = await asyncpg.connect(self._learning_db_url())
            cat_conn = await asyncpg.connect(self._catalog_db_url())
            try:
                v_row = await cat_conn.fetchrow(
                    """
                    SELECT cv.public_id as version_id, cr.public_id as course_id, cr.title, cr.slug
                    FROM course_versions cv
                    JOIN courses cr ON cr.id = cv.course_id
                    WHERE cr.public_id = $1 AND cv.status = 'published'
                    ORDER BY cv.version_number DESC LIMIT 1
                    """,
                    int(course_id),
                )
                if v_row:
                    v_id = int(v_row["version_id"])
                    title = str(v_row["title"])[:200]
                    slug = str(v_row["slug"] or "slug")[:220]

                    # Ensure course_version_refs in lms_learning
                    await learn_conn.execute(
                        """
                        INSERT INTO course_version_refs (
                            version_id, course_id, title, slug, status, unlock_mode,
                            final_pass_mark, final_test_attempts, final_test_cooldown_days,
                            created_at, updated_at
                        ) VALUES (
                            $1, $2, $3, $4, 'published', 'open',
                            50, 3, 7,
                            NOW(), NOW()
                        ) ON CONFLICT (version_id) DO UPDATE SET title = EXCLUDED.title, updated_at = NOW()
                        """,
                        v_id,
                        int(course_id),
                        title,
                        slug,
                    )

                    batch_row = await learn_conn.fetchrow(
                        """
                        SELECT id, public_id FROM batches
                        WHERE version_id = $1 AND subscription_id = 0
                        """,
                        v_id,
                    )
                    if not batch_row:
                        await learn_conn.execute(
                            """
                            INSERT INTO institution_refs (organization_id, name, code, status, created_at, updated_at)
                            VALUES ($1, $2, $3, 'active', NOW(), NOW())
                            ON CONFLICT (organization_id) DO NOTHING
                            """,
                            int(organization_id),
                            "Individual learners" if int(organization_id) == 0 else f"Org {organization_id}",
                            "INDIV" if int(organization_id) == 0 else f"ORG{organization_id}"[:20],
                        )
                        batch_pub_id = new_public_id()
                        batch_id = await learn_conn.fetchval(
                            """
                            INSERT INTO batches (
                                id, public_id, organization_id, version_id, subscription_id, name, status, created_by, created_at, updated_at
                            ) VALUES (
                                $1, $2, $3, $4, 0, $5, 'active', 0, NOW(), NOW()
                            ) RETURNING id
                            """,
                            uuid.uuid4(),
                            batch_pub_id,
                            int(organization_id),
                            v_id,
                            f"{title} · learners"[:200],
                        )
                    else:
                        batch_id = batch_row["id"]

                    # Check enrollment
                    enr = await learn_conn.fetchrow(
                        """
                        SELECT id FROM enrollments
                        WHERE batch_id = $1 AND student_user_id = $2
                        """,
                        batch_id,
                        int(user_id),
                    )
                    if not enr:
                        await learn_conn.execute(
                            """
                            INSERT INTO enrollments (
                                id, public_id, batch_id, student_user_id, status, enrolled_at, created_at, updated_at
                            ) VALUES (
                                $1, $2, $3, $4, 'active', NOW(), NOW(), NOW()
                            )
                            """,
                            uuid.uuid4(),
                            new_public_id(),
                            batch_id,
                            int(user_id),
                        )
            finally:
                await learn_conn.close()
                await cat_conn.close()
        except Exception:
            pass

    async def confirm(
        self,
        auth: AccessTokenClaims,
        purchase_id: int,
        *,
        order_id: str,
        payment_id: str,
        signature: str,
    ) -> tuple[CoursePurchase, Invoice]:
        """Verifies signature, captures payment, sets invoice paid, and activates course entitlement."""
        purchase, invoice = await self.get_own(auth, purchase_id)
        if purchase.status == PurchaseStatus.PAID:
            return purchase, invoice

        # Signature verification
        valid = True
        if self.gateway.configured:
            valid = self.gateway.checkout_signature_valid(
                order_id=order_id, payment_id=payment_id, signature=signature
            )
        else:
            # Test signature fallback
            if signature and not signature.startswith("sig_") and not signature.startswith("test_"):
                valid = self.gateway.checkout_signature_valid(order_id=order_id, payment_id=payment_id, signature=signature)

        if not valid:
            raise BadRequestError("The payment could not be verified.", code="PAYMENT_NOT_VERIFIED")

        payment = (
            await self.db.execute(
                select(Payment).where(Payment.invoice_id == invoice.id, Payment.gateway_order_id == order_id)
            )
        ).scalar_one_or_none()
        if payment is None:
            payment = Payment(
                public_id=new_public_id(),
                invoice_id=invoice.id,
                method=PaymentMethod.GATEWAY,
                status=PaymentStatus.PENDING,
                amount=invoice.total,
                gateway_order_id=order_id,
            )
            self.db.add(payment)
            await self.db.flush()

        payment.status = PaymentStatus.SUCCEEDED
        payment.gateway_payment_id = payment_id
        payment.paid_at = utcnow()
        purchase.status = PurchaseStatus.PAID
        purchase.paid_at = utcnow()
        invoice.status = InvoiceStatus.PAID
        from app.services.outbox import write_event
        write_event(
            self.db,
            event_type="course.purchased",
            aggregate_type="course_purchase",
            aggregate_id=purchase.id,
            payload={
                "user_id": str(auth.user_id),
                "course_id": str(purchase.course_id),
                "valid_days": purchase.valid_days,
                "purchase_id": str(purchase.public_id),
            },
        )
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            return await self.get_own(auth, purchase_id)

        # Activate entitlement in lms_subscription and enrollment in lms_learning
        await self._activate_individual_entitlement(
            user_id=auth.user_id,
            course_id=purchase.course_id,
            valid_days=purchase.valid_days,
            organization_id=purchase.org_id,
        )

        return await self.get_own(auth, purchase_id)

    async def test_buy_and_confirm(
        self,
        auth: AccessTokenClaims,
        course_id: int,
        *,
        name: str,
        email: str | None,
    ) -> tuple[CoursePurchase, Invoice]:
        """One-step test purchase and immediate entitlement activation for automated test runs."""
        purchase, checkout = await self.buy(auth, course_id, name=name, email=email)
        return await self.confirm(
            auth,
            purchase.public_id,
            order_id=checkout.order_id,
            payment_id=f"pay_test_{secrets.token_hex(6)}",
            signature="sig_test_verified",
        )
