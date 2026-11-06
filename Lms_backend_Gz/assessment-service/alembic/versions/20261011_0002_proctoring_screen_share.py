"""tests: proctoring_screen_share

Revision ID: 20261011_0002
Revises: b85fc4b3b132
Create Date: 2026-10-11 13:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261011_0002"
down_revision: str | None = "b85fc4b3b132"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tests", sa.Column("proctoring_screen_share", sa.Boolean(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("tests", "proctoring_screen_share")
