"""Internships: monthly stipend and duration.

Revision ID: 0002_internship_stipend
Revises: 403e4d2de183
Create Date: 2026-10-13 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_internship_stipend"
down_revision: str | None = "403e4d2de183"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("stipend_per_month", sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column("duration_months", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("duration_months")
        batch.drop_column("stipend_per_month")
