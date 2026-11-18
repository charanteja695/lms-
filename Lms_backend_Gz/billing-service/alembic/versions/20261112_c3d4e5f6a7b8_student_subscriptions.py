"""Student subscription plans, payment settings, student subscriptions, and payment transactions.

Revision ID: c3d4e5f6a7b8
Revises: b2c1a0d4e5f6
Create Date: 2026-11-12 10:55:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.db.types import JSONType

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c1a0d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("price_paise", sa.BigInteger(), nullable=False),
        sa.Column("min_price_paise", sa.BigInteger(), nullable=True),
        sa.Column("max_price_paise", sa.BigInteger(), nullable=True),
        sa.Column("billing_duration_days", sa.Integer(), nullable=False),
        sa.Column("billing_label", sa.String(length=40), nullable=False),
        sa.Column("max_courses", sa.Integer(), nullable=True),
        sa.Column("features", JSONType, nullable=False),
        sa.Column("course_access_rules", JSONType, nullable=False),
        sa.Column("assessment_access", JSONType, nullable=False),
        sa.Column("certificate_level", sa.String(length=40), nullable=False),
        sa.Column("support_tier", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_recommended", sa.Boolean(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("tier_rank", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscription_plans")),
        sa.UniqueConstraint("public_id", name=op.f("uq_subscription_plans_public_id")),
        sa.UniqueConstraint("code", name=op.f("uq_subscription_plans_code")),
    )
    op.create_index("ix_subscription_plans_active_order", "subscription_plans", ["is_active", "display_order"], unique=False)

    op.create_table(
        "payment_settings",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("payments_enabled", sa.Boolean(), nullable=False),
        sa.Column("min_amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("max_amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("accepted_methods", JSONType, nullable=False),
        sa.Column("tax_rate_percent", sa.Integer(), nullable=False),
        sa.Column("upgrade_pricing_mode", sa.String(length=30), nullable=False),
        sa.Column("upi_vpa", sa.String(length=120), nullable=False),
        sa.Column("upi_merchant_name", sa.String(length=120), nullable=False),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_settings")),
    )

    op.create_table(
        "student_subscriptions",
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("plan_code", sa.String(length=40), nullable=False),
        sa.Column("plan_name", sa.String(length=120), nullable=False),
        sa.Column("price_paise", sa.BigInteger(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("max_courses", sa.Integer(), nullable=True),
        sa.Column("features_snapshot", JSONType, nullable=False),
        sa.Column("assessment_access_snapshot", JSONType, nullable=False),
        sa.Column("certificate_level", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_subscription_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], name=op.f("fk_student_subscriptions_plan_id_subscription_plans"), ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_subscriptions")),
        sa.UniqueConstraint("public_id", name=op.f("uq_student_subscriptions_public_id")),
    )
    op.create_index("ix_student_subscriptions_user_status", "student_subscriptions", ["user_id", "status"], unique=False)
    op.create_index("ix_student_subscriptions_status_ends", "student_subscriptions", ["status", "ends_at"], unique=False)

    op.create_table(
        "student_subscription_courses",
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("course_title", sa.String(length=200), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["subscription_id"], ["student_subscriptions.id"], name=op.f("fk_student_subscription_courses_subscription_id_student_subscriptions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_subscription_courses")),
        sa.UniqueConstraint("subscription_id", "course_id", name="uq_sub_courses_sub_course"),
    )
    op.create_index("ix_student_subscription_courses_user_course", "student_subscription_courses", ["user_id", "course_id"], unique=False)

    op.create_table(
        "student_payment_transactions",
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("transaction_ref", sa.String(length=60), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("plan_code", sa.String(length=40), nullable=False),
        sa.Column("plan_name", sa.String(length=120), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("course_title", sa.String(length=200), nullable=True),
        sa.Column("action_type", sa.String(length=20), nullable=False),
        sa.Column("original_amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("discount_paise", sa.BigInteger(), nullable=False),
        sa.Column("tax_paise", sa.BigInteger(), nullable=False),
        sa.Column("total_amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payment_method", sa.String(length=40), nullable=False),
        sa.Column("gateway_provider", sa.String(length=30), nullable=False),
        sa.Column("gateway_order_id", sa.String(length=100), nullable=False),
        sa.Column("gateway_payment_id", sa.String(length=100), nullable=True),
        sa.Column("gateway_signature", sa.String(length=200), nullable=True),
        sa.Column("upi_qr_payload", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("failure_reason", sa.String(length=300), nullable=True),
        sa.Column("invoice_id", sa.Uuid(), nullable=True),
        sa.Column("invoice_number", sa.String(length=30), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], name=op.f("fk_student_payment_transactions_invoice_id_invoices"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], name=op.f("fk_student_payment_transactions_plan_id_subscription_plans"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subscription_id"], ["student_subscriptions.id"], name=op.f("fk_student_payment_transactions_subscription_id_student_subscriptions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_payment_transactions")),
        sa.UniqueConstraint("gateway_order_id", name=op.f("uq_student_payment_transactions_gateway_order_id")),
        sa.UniqueConstraint("gateway_payment_id", name=op.f("uq_student_payment_transactions_gateway_payment_id")),
        sa.UniqueConstraint("public_id", name=op.f("uq_student_payment_transactions_public_id")),
        sa.UniqueConstraint("transaction_ref", name=op.f("uq_student_payment_transactions_transaction_ref")),
    )
    op.create_index("ix_student_payment_tx_user_created", "student_payment_transactions", ["user_id", "created_at"], unique=False)
    op.create_index("ix_student_payment_tx_status", "student_payment_transactions", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_student_payment_tx_status", table_name="student_payment_transactions")
    op.drop_index("ix_student_payment_tx_user_created", table_name="student_payment_transactions")
    op.drop_table("student_payment_transactions")
    op.drop_index("ix_student_subscription_courses_user_course", table_name="student_subscription_courses")
    op.drop_table("student_subscription_courses")
    op.drop_index("ix_student_subscriptions_status_ends", table_name="student_subscriptions")
    op.drop_index("ix_student_subscriptions_user_status", table_name="student_subscriptions")
    op.drop_table("student_subscriptions")
    op.drop_table("payment_settings")
    op.drop_index("ix_subscription_plans_active_order", table_name="subscription_plans")
    op.drop_table("subscription_plans")
