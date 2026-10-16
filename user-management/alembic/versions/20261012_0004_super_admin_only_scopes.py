"""Courses, tests, exams, jobs, billing and AI become the super admin's alone: drop those scopes from admins.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-12 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of roles.ADMIN_SCOPES at this revision.
_ADMIN_SCOPES = ("accounts.manage", "analytics.view", "support.manage")


def upgrade() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, scopes FROM users WHERE role = 'admin' AND scopes IS NOT NULL"))
    for user_id, stored in rows.fetchall():
        kept = sorted({scope for scope in stored.split(",") if scope in _ADMIN_SCOPES})
        value = f",{','.join(kept)}," if kept else None
        if value != stored:
            connection.execute(
                sa.text("UPDATE users SET scopes = :scopes, token_version = token_version + 1 WHERE id = :id"),
                {"scopes": value, "id": user_id},
            )


def downgrade() -> None:
    """The removed scopes are not restored: the super admin re-grants them if this is rolled back."""
