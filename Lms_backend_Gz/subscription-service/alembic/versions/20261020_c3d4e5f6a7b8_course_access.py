"""A self-registered learner's bought access to a course (course.purchased from billing-service).

Revision ID: c3d4e5f6a7b8
Revises: e65de82fc66a
Create Date: 2026-10-20 14:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "e65de82fc66a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "course_access",
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("organization_id", sa.BigInteger(), nullable=False),
        sa.Column("course_id", sa.BigInteger(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="active", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_course_access")),
    )
    op.create_index(op.f("ix_course_access_public_id"), "course_access", ["public_id"], unique=True)
    op.create_index("uq_course_access_user_course", "course_access", ["user_id", "course_id"], unique=True)
    op.create_index("ix_course_access_status_ends_at", "course_access", ["status", "ends_at"])
    op.create_table(
        "course_access_purchases",
        sa.Column("purchase_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("access_id", sa.Uuid(), nullable=False),
        sa.Column("valid_days", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["access_id"], ["course_access.id"], name=op.f("fk_course_access_purchases_access_id_course_access"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("purchase_id", name=op.f("pk_course_access_purchases")),
    )


def downgrade() -> None:
    op.drop_table("course_access_purchases")
    op.drop_index("ix_course_access_status_ends_at", table_name="course_access")
    op.drop_index("uq_course_access_user_course", table_name="course_access")
    op.drop_index(op.f("ix_course_access_public_id"), table_name="course_access")
    op.drop_table("course_access")
