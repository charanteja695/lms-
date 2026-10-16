"""message attachments

Revision ID: 20261011_0002
Revises: f6bba901df14
Create Date: 2026-10-11 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20261011_0002"
down_revision: str | None = "f6bba901df14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ticket_messages",
        sa.Column("attachments", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ticket_messages", "attachments")
