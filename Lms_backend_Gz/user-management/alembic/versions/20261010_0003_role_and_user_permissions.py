"""Role permission defaults and per-person permission grants/removals.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("permission", sa.String(length=64), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_role_permissions")),
    )
    op.create_index("uq_role_permissions_role_permission", "role_permissions", ["role", "permission"], unique=True)
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("permission", sa.String(length=64), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=True),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_permissions_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_permissions")),
    )
    op.create_index("uq_user_permissions_user_id_permission", "user_permissions", ["user_id", "permission"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_user_permissions_user_id_permission", table_name="user_permissions")
    op.drop_table("user_permissions")
    op.drop_index("uq_role_permissions_role_permission", table_name="role_permissions")
    op.drop_table("role_permissions")
