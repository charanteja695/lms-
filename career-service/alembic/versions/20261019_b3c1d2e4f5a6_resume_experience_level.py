"""resume experience level

Revision ID: b3c1d2e4f5a6
Revises: 8fa456e94e78
Create Date: 2026-10-19 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b3c1d2e4f5a6"
down_revision: str | None = "8fa456e94e78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("resumes", sa.Column("experience_level", sa.String(length=10), server_default="fresher", nullable=False))


def downgrade() -> None:
    op.drop_column("resumes", "experience_level")
