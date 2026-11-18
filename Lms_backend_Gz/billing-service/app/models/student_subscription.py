"""Student subscription plans, payment settings, active student subscriptions, and payment transactions."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType
from app.domain.enums import StudentSubStatus, TxStatus


class SubscriptionPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Admin-configurable subscription plans (Base, Silver, Gold, or custom)."""

    __tablename__ = "subscription_plans"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    price_paise: Mapped[int] = mapped_column(BigInteger)
    min_price_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    max_price_paise: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    billing_duration_days: Mapped[int] = mapped_column(Integer, default=30)
    billing_label: Mapped[str] = mapped_column(String(40), default="month")
    max_courses: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = unlimited
    features: Mapped[list[str]] = mapped_column(JSONType, default=list)
    course_access_rules: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    assessment_access: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    certificate_level: Mapped[str] = mapped_column(String(40), default="basic")  # none | basic | premium | pro
    support_tier: Mapped[str] = mapped_column(String(80), default="Email Support")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    tier_rank: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (Index("ix_subscription_plans_active_order", "is_active", "display_order"),)


class PaymentSettings(TimestampMixin, Base):
    """Singleton payment gateway & pricing settings managed by Admin."""

    __tablename__ = "payment_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False, default=1)
    payments_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    min_amount_paise: Mapped[int] = mapped_column(BigInteger, default=49900)
    max_amount_paise: Mapped[int] = mapped_column(BigInteger, default=499900)
    accepted_methods: Mapped[dict[str, bool]] = mapped_column(JSONType, default=dict)
    tax_rate_percent: Mapped[int] = mapped_column(Integer, default=0)
    upgrade_pricing_mode: Mapped[str] = mapped_column(String(30), default="price_difference")  # price_difference | full_price
    upi_vpa: Mapped[str] = mapped_column(String(120), default="examlms@icici")
    upi_merchant_name: Mapped[str] = mapped_column(String(120), default="ExamLMS")
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class StudentSubscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One student's subscription purchase, upgrade, or renewal."""

    __tablename__ = "student_subscriptions"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int] = mapped_column(BigInteger, default=0)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscription_plans.id", ondelete="RESTRICT"))
    plan_code: Mapped[str] = mapped_column(String(40))
    plan_name: Mapped[str] = mapped_column(String(120))
    price_paise: Mapped[int] = mapped_column(BigInteger)
    duration_days: Mapped[int] = mapped_column(Integer)
    max_courses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    features_snapshot: Mapped[list[str]] = mapped_column(JSONType, default=list)
    assessment_access_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    certificate_level: Mapped[str] = mapped_column(String(40), default="basic")
    status: Mapped[str] = mapped_column(String(20), default=StudentSubStatus.PENDING)
    starts_at: Mapped[datetime | None]
    ends_at: Mapped[datetime | None]
    replaced_subscription_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_student_subscriptions_user_status", "user_id", "status"),
        Index("ix_student_subscriptions_status_ends", "status", "ends_at"),
    )


class StudentSubscriptionCourse(UUIDPrimaryKeyMixin, Base):
    """Courses unlocked under a specific student subscription."""

    __tablename__ = "student_subscription_courses"

    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("student_subscriptions.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger)
    course_id: Mapped[int] = mapped_column(BigInteger)
    course_title: Mapped[str] = mapped_column(String(200), default="")
    granted_at: Mapped[datetime]

    __table_args__ = (
        UniqueConstraint("subscription_id", "course_id", name="uq_sub_courses_sub_course"),
        Index("ix_student_subscription_courses_user_course", "user_id", "course_id"),
    )


class StudentPaymentTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Student payment transaction ledger (never stores raw card numbers or CVVs)."""

    __tablename__ = "student_payment_transactions"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    transaction_ref: Mapped[str] = mapped_column(String(60), unique=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    payer_user_id: Mapped[int] = mapped_column(BigInteger, default=0)
    payer_role: Mapped[str] = mapped_column(String(30), default="student")
    payment_scope: Mapped[str] = mapped_column(String(30), default="independent_student")
    student_count: Mapped[int] = mapped_column(Integer, default=1)
    organization_id: Mapped[int] = mapped_column(BigInteger, default=0)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("student_subscriptions.id", ondelete="CASCADE"), nullable=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscription_plans.id", ondelete="RESTRICT"))
    plan_code: Mapped[str] = mapped_column(String(40))
    plan_name: Mapped[str] = mapped_column(String(120))
    course_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    course_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    action_type: Mapped[str] = mapped_column(String(20), default="new")
    original_amount_paise: Mapped[int] = mapped_column(BigInteger)
    discount_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    tax_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    total_amount_paise: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    payment_method: Mapped[str] = mapped_column(String(40), default="upi")
    gateway_provider: Mapped[str] = mapped_column(String(30), default="razorpay")
    gateway_order_id: Mapped[str] = mapped_column(String(100), unique=True)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    gateway_signature: Mapped[str | None] = mapped_column(String(200), nullable=True)
    upi_qr_payload: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=TxStatus.PENDING)
    failure_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    expires_at: Mapped[datetime | None]
    paid_at: Mapped[datetime | None]

    __table_args__ = (
        Index("ix_student_payment_tx_user_created", "user_id", "created_at"),
        Index("ix_student_payment_tx_status", "status"),
        Index("ix_student_payment_tx_org_created", "organization_id", "created_at"),
    )


class StudentPaymentRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Payment request raised by an institution-managed student for Institution Head approval & payment."""

    __tablename__ = "student_payment_requests"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    request_ref: Mapped[str] = mapped_column(String(60), unique=True)
    student_user_id: Mapped[int] = mapped_column(BigInteger)
    student_name: Mapped[str] = mapped_column(String(200), default="")
    student_email: Mapped[str] = mapped_column(String(255), default="")
    organization_id: Mapped[int] = mapped_column(BigInteger)
    course_id: Mapped[int] = mapped_column(BigInteger)
    course_title: Mapped[str] = mapped_column(String(200), default="")
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscription_plans.id", ondelete="RESTRICT"))
    plan_code: Mapped[str] = mapped_column(String(40))
    plan_name: Mapped[str] = mapped_column(String(120))
    amount_paise: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    student_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reviewed_at: Mapped[datetime | None]
    paid_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    paid_at: Mapped[datetime | None]
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("student_payment_transactions.id", ondelete="SET NULL"), nullable=True)
    allocation_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_student_pay_req_org_status", "organization_id", "status", "created_at"),
        Index("ix_student_pay_req_student", "student_user_id", "created_at"),
    )


class StudentPaymentAllocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-student payment allocation under a single or bulk transaction."""

    __tablename__ = "student_payment_allocations"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("student_payment_transactions.id", ondelete="CASCADE"))
    organization_id: Mapped[int] = mapped_column(BigInteger, default=0)
    payer_user_id: Mapped[int] = mapped_column(BigInteger)
    student_user_id: Mapped[int] = mapped_column(BigInteger)
    student_name: Mapped[str] = mapped_column(String(200), default="")
    student_email: Mapped[str] = mapped_column(String(255), default="")
    course_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    course_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscription_plans.id", ondelete="RESTRICT"))
    plan_code: Mapped[str] = mapped_column(String(40))
    plan_name: Mapped[str] = mapped_column(String(120))
    payment_request_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("student_payment_requests.id", ondelete="SET NULL"), nullable=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("student_subscriptions.id", ondelete="SET NULL"), nullable=True)
    original_amount_paise: Mapped[int] = mapped_column(BigInteger)
    discount_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    tax_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    allocated_amount_paise: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default=TxStatus.PENDING)
    activated_at: Mapped[datetime | None]

    __table_args__ = (
        UniqueConstraint("transaction_id", "student_user_id", name="uq_student_alloc_tx_student"),
        Index("ix_student_alloc_student_status", "student_user_id", "status"),
        Index("ix_student_alloc_org_created", "organization_id", "created_at"),
    )
