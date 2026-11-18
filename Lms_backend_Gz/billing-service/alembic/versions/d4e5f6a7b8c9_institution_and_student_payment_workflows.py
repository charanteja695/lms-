"""institution and student payment workflows

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-12 11:50:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_payment_transactions", sa.Column("payer_user_id", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("student_payment_transactions", sa.Column("payer_role", sa.String(length=30), nullable=False, server_default="student"))
    op.add_column("student_payment_transactions", sa.Column("payment_scope", sa.String(length=30), nullable=False, server_default="independent_student"))
    op.add_column("student_payment_transactions", sa.Column("student_count", sa.Integer(), nullable=False, server_default="1"))
    op.alter_column("student_payment_transactions", "subscription_id", existing_type=sa.Uuid(), nullable=True)
    op.create_index("ix_student_payment_tx_org_created", "student_payment_transactions", ["organization_id", "created_at"])

    op.create_table(
        "student_payment_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("request_ref", sa.String(length=60), nullable=False),
        sa.Column("student_user_id", sa.BigInteger(), nullable=False),
        sa.Column("student_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("student_email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("course_title", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("plan_code", sa.String(length=40), nullable=False),
        sa.Column("plan_name", sa.String(length=120), nullable=False),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("student_note", sa.String(length=500), nullable=True),
        sa.Column("decision_note", sa.String(length=500), nullable=True),
        sa.Column("reviewed_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_id", sa.Uuid(), nullable=True),
        sa.Column("allocation_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["transaction_id"], ["student_payment_transactions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("request_ref"),
    )
    op.create_index("ix_student_pay_req_org_status", "student_payment_requests", ["organization_id", "status", "created_at"])
    op.create_index("ix_student_pay_req_student", "student_payment_requests", ["student_user_id", "created_at"])

    op.create_table(
        "student_payment_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("transaction_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("payer_user_id", sa.BigInteger(), nullable=False),
        sa.Column("student_user_id", sa.BigInteger(), nullable=False),
        sa.Column("student_name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("student_email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("course_id", sa.BigInteger(), nullable=True),
        sa.Column("course_title", sa.String(length=200), nullable=True),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("plan_code", sa.String(length=40), nullable=False),
        sa.Column("plan_name", sa.String(length=120), nullable=False),
        sa.Column("payment_request_id", sa.Uuid(), nullable=True),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        sa.Column("original_amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("discount_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tax_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("allocated_amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["payment_request_id"], ["student_payment_requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subscription_id"], ["student_subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["transaction_id"], ["student_payment_transactions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
        sa.UniqueConstraint("transaction_id", "student_user_id", name="uq_student_alloc_tx_student"),
    )
    op.create_index("ix_student_alloc_student_status", "student_payment_allocations", ["student_user_id", "status"])
    op.create_index("ix_student_alloc_org_created", "student_payment_allocations", ["organization_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_student_alloc_org_created", table_name="student_payment_allocations")
    op.drop_index("ix_student_alloc_student_status", table_name="student_payment_allocations")
    op.drop_table("student_payment_allocations")
    op.drop_index("ix_student_pay_req_student", table_name="student_payment_requests")
    op.drop_index("ix_student_pay_req_org_status", table_name="student_payment_requests")
    op.drop_table("student_payment_requests")
    op.drop_index("ix_student_payment_tx_org_created", table_name="student_payment_transactions")
    op.alter_column("student_payment_transactions", "subscription_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("student_payment_transactions", "student_count")
    op.drop_column("student_payment_transactions", "payment_scope")
    op.drop_column("student_payment_transactions", "payer_role")
    op.drop_column("student_payment_transactions", "payer_user_id")
