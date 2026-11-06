"""Add Job Description fields and migrate existing descriptions.

Revision ID: 0004_job_description_fields
Revises: 0003_corporate_job_details
Create Date: 2026-10-30 17:15:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from app.db.types import JSONType

revision: str = "0004_job_description_fields"
down_revision: str | None = "0003_corporate_job_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("banner_text", sa.Text(), nullable=True))
        batch.add_column(sa.Column("banner_type", sa.String(20), nullable=True, server_default="info"))
        batch.add_column(sa.Column("experience_level", sa.String(20), nullable=True))
        batch.add_column(sa.Column("experience_level_description", sa.Text(), nullable=True))
        batch.add_column(sa.Column("about_job", sa.Text(), nullable=True))
        batch.add_column(sa.Column("responsibilities", JSONType, nullable=True, server_default="[]"))
        batch.add_column(sa.Column("minimum_qualifications", JSONType, nullable=True, server_default="[]"))
        batch.add_column(sa.Column("preferred_qualifications", JSONType, nullable=True, server_default="[]"))
        batch.add_column(sa.Column("perks", JSONType, nullable=True, server_default="[]"))

    # Data migration: copy old description into about_job where about_job is null/empty
    op.execute(
        sa.text(
            "UPDATE jobs SET about_job = description "
            "WHERE (about_job IS NULL OR about_job = '') AND description IS NOT NULL"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_column("perks")
        batch.drop_column("preferred_qualifications")
        batch.drop_column("minimum_qualifications")
        batch.drop_column("responsibilities")
        batch.drop_column("about_job")
        batch.drop_column("experience_level_description")
        batch.drop_column("experience_level")
        batch.drop_column("banner_type")
        batch.drop_column("banner_text")
