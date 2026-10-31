"""Corporate job descriptions and recruitment workflows.

Revision ID: 0003_corporate_job_details
Revises: 0002_internship_stipend
Create Date: 2026-10-28 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from app.db.types import JSONType

revision: str = "0003_corporate_job_details"
down_revision: str | None = "0002_internship_stipend"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("job_code", sa.String(32), nullable=True))
        batch.add_column(sa.Column("job_details", JSONType, nullable=True, server_default="{}"))
        batch.add_column(sa.Column("hiring_process", JSONType, nullable=True, server_default="[]"))
        batch.add_column(sa.Column("application_config", JSONType, nullable=True, server_default="{}"))

    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("answers", JSONType, nullable=True, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.drop_column("answers")

    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("application_config")
        batch.drop_column("hiring_process")
        batch.drop_column("job_details")
        batch.drop_column("job_code")
