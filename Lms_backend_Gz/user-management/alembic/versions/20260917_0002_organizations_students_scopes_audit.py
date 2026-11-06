"""Employers and admin scopes, student academic profile, optional student email, audit log ids, import results.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-17 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op
from app.core.ids import _EPOCH_MS, _RANDOM_BITS

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def _batch(table: str):
    """SQLite cannot ALTER columns, so batch mode rebuilds the table there (local development)."""
    recreate = "always" if op.get_bind().dialect.name == "sqlite" else "auto"
    return op.batch_alter_table(table, recreate=recreate)


def upgrade() -> None:
    # --- users: optional email (students), admin scopes (existing admins keep managing institutions)
    with _batch("users") as batch:
        batch.alter_column("email", existing_type=sa.String(length=254), nullable=True)
        batch.add_column(sa.Column("scopes", sa.String(length=500), nullable=True))
    op.execute("UPDATE users SET scopes = ',accounts.manage,' WHERE role = 'admin'")

    # --- organisations: institutions and employers share one table
    with _batch("institutions") as batch:
        batch.add_column(sa.Column("org_type", sa.String(length=20), server_default="institution", nullable=False))
        batch.add_column(sa.Column("industry", sa.String(length=100), nullable=True))
        batch.alter_column("institution_type", existing_type=sa.String(length=40), nullable=True)
    op.create_index("ix_institutions_org_type_created_at", "institutions", ["org_type", "created_at"], unique=False)

    # --- students: academic placement
    with _batch("student_profiles") as batch:
        batch.add_column(sa.Column("program", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("branch", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("year_of_study", sa.SmallInteger(), nullable=True))
        batch.add_column(sa.Column("section", sa.String(length=20), nullable=True))
        batch.add_column(sa.Column("graduation_year", sa.SmallInteger(), nullable=True))
        batch.add_column(sa.Column("cgpa", sa.Numeric(precision=4, scale=2), nullable=True))
    op.create_index(
        "ix_student_profiles_institution_graduation_branch",
        "student_profiles",
        ["institution_id", "graduation_year", "branch"],
        unique=False,
    )

    # --- audit log: public audit_log_id (backfilled in the same format as every other public id)
    op.add_column("audit_logs", sa.Column("public_id", sa.BigInteger(), nullable=True))
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            f"UPDATE audit_logs SET public_id = "
            f"((floor(extract(epoch FROM created_at) * 1000)::bigint - {_EPOCH_MS}) << {_RANDOM_BITS}) "
            f"| floor(random() * {2**_RANDOM_BITS})::bigint"
        )
    else:
        rows = op.get_bind().execute(sa.text("SELECT id FROM audit_logs")).fetchall()
        from app.core.ids import new_public_id

        for (row_id,) in rows:
            op.get_bind().execute(
                sa.text("UPDATE audit_logs SET public_id = :value WHERE id = :id"), {"value": new_public_id(), "id": row_id}
            )
    with _batch("audit_logs") as batch:
        batch.alter_column("public_id", existing_type=sa.BigInteger(), nullable=False)
    op.create_index("uq_audit_logs_public_id", "audit_logs", ["public_id"], unique=True)
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)

    # --- background jobs: import summary
    op.add_column("background_jobs", sa.Column("result", JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("background_jobs", "result")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("uq_audit_logs_public_id", table_name="audit_logs")
    with _batch("audit_logs") as batch:
        batch.drop_column("public_id")
    op.drop_index("ix_student_profiles_institution_graduation_branch", table_name="student_profiles")
    with _batch("student_profiles") as batch:
        for column in ("cgpa", "graduation_year", "section", "year_of_study", "branch", "program"):
            batch.drop_column(column)
    op.drop_index("ix_institutions_org_type_created_at", table_name="institutions")
    op.execute("DELETE FROM institutions WHERE org_type <> 'institution'")
    with _batch("institutions") as batch:
        batch.alter_column("institution_type", existing_type=sa.String(length=40), nullable=False)
        batch.drop_column("industry")
        batch.drop_column("org_type")
    with _batch("users") as batch:
        batch.drop_column("scopes")
        batch.alter_column("email", existing_type=sa.String(length=254), nullable=False)
