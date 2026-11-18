"""add course pricing change audits

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-16 10:15:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "course_pricing_change_audits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("course_title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("previous_individual_price_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("new_individual_price_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("previous_institutional_price_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("new_institutional_price_paise", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("pricing_method", sa.String(length=30), nullable=False, server_default="fixed"),
        sa.Column("gst_percent", sa.Integer(), nullable=False, server_default="18"),
        sa.Column("admin_user_id", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("admin_email", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_course_pricing_audit_cid", "course_pricing_change_audits", ["course_id", "created_at"])
    op.create_index("ix_course_pricing_audit_public_id", "course_pricing_change_audits", ["public_id"], unique=True)


def downgrade() -> None:
    op.drop_table("course_pricing_change_audits")
