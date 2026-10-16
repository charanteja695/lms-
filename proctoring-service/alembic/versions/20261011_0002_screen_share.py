"""screen sharing: per test (read model) and per session

Revision ID: 20261011_0002
Revises: b89a5fedfed3
Create Date: 2026-10-11 13:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261011_0002"
down_revision: str | None = "b89a5fedfed3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("test_refs", sa.Column("screen_share", sa.Boolean(), server_default="0", nullable=False))
    op.add_column("proctor_sessions", sa.Column("screen_share", sa.Boolean(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("proctor_sessions", "screen_share")
    op.drop_column("test_refs", "screen_share")
