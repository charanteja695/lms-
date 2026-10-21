"""Individual learners buy courses: one row per purchase, invoiced at once, access granted when paid.

Revision ID: b2c1a0d4e5f6
Revises: 90993ec618b3
Create Date: 2026-10-20 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c1a0d4e5f6"
down_revision: str | None = "90993ec618b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_purchases",
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("org_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("course_name", sa.String(length=160), nullable=False),
        sa.Column("valid_days", sa.Integer(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], name=op.f("fk_course_purchases_invoice_id_invoices"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_purchases")),
        sa.UniqueConstraint("public_id", name=op.f("uq_course_purchases_public_id")),
    )
    op.create_index("ix_course_purchases_user_status", "course_purchases", ["user_id", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_course_purchases_user_status", table_name="course_purchases")
    op.drop_table("course_purchases")
