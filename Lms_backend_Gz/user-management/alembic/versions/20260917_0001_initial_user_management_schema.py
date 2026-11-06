"""Initial user management schema: users, profiles, guardians, institutions, sessions, password resets, audit log, outbox.

Revision ID: 0001
Revises:
Create Date: 2026-09-17 07:45:57.502351
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TRIGRAM_INDEXES = (
    ("ix_users_email_trgm", "users", "email"),
    ("ix_users_username_trgm", "users", "username"),
    ("ix_users_first_name_trgm", "users", "first_name"),
    ("ix_users_last_name_trgm", "users", "last_name"),
    ("ix_users_phone_trgm", "users", "phone"),
    ("ix_employment_profiles_employee_code_trgm", "employment_profiles", "employee_code"),
    ("ix_student_profiles_admission_number_trgm", "student_profiles", "admission_number"),
)


def _create_trigram_indexes() -> None:
    """Trigram (pg_trgm) GIN indexes keep "contains" search fast on millions of rows.

    pg_trgm ships with standard PostgreSQL (Docker images, RDS, Cloud SQL, Azure). If a server lacks
    it, the schema is still created and search still works, only slower on very large tables.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":  # SQLite (local development) has no extensions
        return
    available = bind.execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'pg_trgm'")).scalar()
    if not available:
        print("WARNING: pg_trgm is not available; skipping trigram search indexes")
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for name, table, column in TRIGRAM_INDEXES:
        op.create_index(name, table, [column], postgresql_using="gin", postgresql_ops={column: "gin_trgm_ops"})


def _drop_trigram_indexes() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for name, table, _ in TRIGRAM_INDEXES:
        op.drop_index(name, table_name=table, if_exists=True)


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=50), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "details", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_action_created_at", "audit_logs", ["action", "created_at"], unique=False)
    op.create_index("ix_audit_logs_actor_id_created_at", "audit_logs", ["actor_id", "created_at"], unique=False)
    op.create_index(
        "ix_audit_logs_institution_id_created_at", "audit_logs", ["institution_id", "created_at"], unique=False
    )
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"], unique=False)
    op.create_table(
        "outbox_events",
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_type", sa.String(length=50), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column(
            "payload", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outbox_events")),
    )
    op.create_index(
        "ix_outbox_events_unpublished",
        "outbox_events",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("published_at IS NULL"),
    )
    op.create_table(
        "users",
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=50), nullable=False),
        sa.Column("middle_name", sa.String(length=50), nullable=True),
        sa.Column("last_name", sa.String(length=50), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("status_reason", sa.String(length=500), nullable=True),
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column("manager_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_users_created_by_id_users"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["manager_id"], ["users.id"], name=op.f("fk_users_manager_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("public_id", name=op.f("uq_users_public_id")),
    )
    op.create_index(
        "ix_users_created_active", "users", ["created_at"], unique=False, postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.create_index(
        "ix_users_created_by_id",
        "users",
        ["created_by_id"],
        unique=False,
        postgresql_where=sa.text("created_by_id IS NOT NULL"),
    )
    op.create_index(
        "ix_users_institution_role_created",
        "users",
        ["institution_id", "role", "created_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_users_manager_id", "users", ["manager_id"], unique=False, postgresql_where=sa.text("manager_id IS NOT NULL")
    )
    op.create_index(
        "ix_users_role_created",
        "users",
        ["role", "created_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_users_email_active", "users", ["email"], unique=True, postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.create_index(
        "uq_users_username_active", "users", ["username"], unique=True, postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.create_table(
        "background_jobs",
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(), nullable=False),
        sa.Column(
            "parameters", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["users.id"], name=op.f("fk_background_jobs_requested_by_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_background_jobs")),
        sa.UniqueConstraint("public_id", name=op.f("uq_background_jobs_public_id")),
    )
    op.create_index(
        "ix_background_jobs_requested_by_id_created_at",
        "background_jobs",
        ["requested_by_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_background_jobs_status_created_at", "background_jobs", ["status", "created_at"], unique=False)
    op.create_table(
        "institutions",
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("institution_type", sa.String(length=40), nullable=False),
        sa.Column("admin_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("alternate_phone", sa.String(length=20), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("address_line1", sa.String(length=255), nullable=False),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("postal_code", sa.String(length=12), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("registration_number", sa.String(length=50), nullable=True),
        sa.Column("affiliation", sa.String(length=100), nullable=True),
        sa.Column("established_year", sa.SmallInteger(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("status_reason", sa.String(length=500), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_id"], ["users.id"], name=op.f("fk_institutions_admin_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_institutions_created_by_id_users"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_institutions")),
        sa.UniqueConstraint("public_id", name=op.f("uq_institutions_public_id")),
    )
    op.create_index("ix_institutions_admin_id_status", "institutions", ["admin_id", "status"], unique=False)
    op.create_index("ix_institutions_created_at", "institutions", ["created_at"], unique=False)
    op.create_index(
        "uq_institutions_code_active",
        "institutions",
        ["code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # users <-> institutions reference each other, so this key is added once both tables exist.
    # SQLite (local development) cannot add a foreign key after the fact, and does not need it.
    if op.get_bind().dialect.name != "sqlite":
        op.create_foreign_key(
            op.f("fk_users_institution_id_institutions"),
            "users",
            "institutions",
            ["institution_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_table(
        "mfa_challenges",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_mfa_challenges_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mfa_challenges")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_mfa_challenges_token_hash")),
    )
    op.create_index("ix_mfa_challenges_user_id", "mfa_challenges", ["user_id"], unique=False)
    op.create_table(
        "mfa_recovery_codes",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_mfa_recovery_codes_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mfa_recovery_codes")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_mfa_recovery_codes_code_hash")),
    )
    op.create_index("ix_mfa_recovery_codes_user_id", "mfa_recovery_codes", ["user_id"], unique=False)
    op.create_table(
        "password_reset_requests",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("otp_hash", sa.String(length=64), nullable=True),
        sa.Column("link_token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reset_token_hash", sa.String(length=64), nullable=True),
        sa.Column("reset_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip", sa.String(length=45), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_password_reset_requests_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_requests")),
        sa.UniqueConstraint("link_token_hash", name=op.f("uq_password_reset_requests_link_token_hash")),
        sa.UniqueConstraint("reset_token_hash", name=op.f("uq_password_reset_requests_reset_token_hash")),
    )
    op.create_index(
        "ix_password_reset_requests_user_id_consumed_at",
        "password_reset_requests",
        ["user_id", "consumed_at"],
        unique=False,
    )
    op.create_table(
        "student_guardians",
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(length=100), nullable=False),
        sa.Column("relationship", sa.String(length=20), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("occupation", sa.String(length=100), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["student_id"], ["users.id"], name=op.f("fk_student_guardians_student_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_student_guardians")),
    )
    op.create_index("ix_student_guardians_student_id", "student_guardians", ["student_id"], unique=False)
    op.create_table(
        "user_mfa",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("secret_encrypted", sa.String(length=255), nullable=True),
        sa.Column("pending_secret_encrypted", sa.String(length=255), nullable=True),
        sa.Column("enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_step", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_mfa_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_mfa")),
    )
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("gender", sa.String(length=20), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("alternate_phone", sa.String(length=20), nullable=True),
        sa.Column("preferred_language", sa.String(length=10), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("state", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=12), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_profiles")),
    )
    op.create_table(
        "user_sessions",
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=50), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
        sa.UniqueConstraint("public_id", name=op.f("uq_user_sessions_public_id")),
    )
    op.create_index("ix_user_sessions_user_id_revoked_at", "user_sessions", ["user_id", "revoked_at"], unique=False)
    op.create_table(
        "employment_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=True),
        sa.Column("employee_code", sa.String(length=30), nullable=True),
        sa.Column("designation", sa.String(length=100), nullable=True),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column("employment_type", sa.String(length=20), nullable=True),
        sa.Column("date_of_joining", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name=op.f("fk_employment_profiles_institution_id_institutions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_employment_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_employment_profiles")),
    )
    op.create_index(
        "uq_employment_profiles_institution_employee_code",
        "employment_profiles",
        ["institution_id", "employee_code"],
        unique=True,
        postgresql_where=sa.text("employee_code IS NOT NULL"),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["user_sessions.id"],
            name=op.f("fk_refresh_tokens_session_id_user_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"], unique=False)
    op.create_table(
        "student_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), nullable=False),
        sa.Column("admission_number", sa.String(length=30), nullable=False),
        sa.Column("admission_date", sa.Date(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"],
            ["institutions.id"],
            name=op.f("fk_student_profiles_institution_id_institutions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_student_profiles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_student_profiles")),
        sa.UniqueConstraint("institution_id", "admission_number", name=op.f("uq_student_profiles_institution_id")),
    )

    _create_trigram_indexes()


def downgrade() -> None:
    _drop_trigram_indexes()
    op.drop_table("student_profiles")
    op.drop_index("ix_refresh_tokens_session_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index(
        "uq_employment_profiles_institution_employee_code",
        table_name="employment_profiles",
        postgresql_where=sa.text("employee_code IS NOT NULL"),
    )
    op.drop_table("employment_profiles")
    op.drop_index("ix_user_sessions_user_id_revoked_at", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_table("user_profiles")
    op.drop_table("user_mfa")
    op.drop_index("ix_student_guardians_student_id", table_name="student_guardians")
    op.drop_table("student_guardians")
    op.drop_index("ix_password_reset_requests_user_id_consumed_at", table_name="password_reset_requests")
    op.drop_table("password_reset_requests")
    op.drop_index("ix_mfa_recovery_codes_user_id", table_name="mfa_recovery_codes")
    op.drop_table("mfa_recovery_codes")
    op.drop_index("ix_mfa_challenges_user_id", table_name="mfa_challenges")
    op.drop_table("mfa_challenges")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(op.f("fk_users_institution_id_institutions"), "users", type_="foreignkey")
    op.drop_index(
        "uq_institutions_code_active", table_name="institutions", postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.drop_index("ix_institutions_created_at", table_name="institutions")
    op.drop_index("ix_institutions_admin_id_status", table_name="institutions")
    op.drop_table("institutions")
    op.drop_index("ix_background_jobs_status_created_at", table_name="background_jobs")
    op.drop_index("ix_background_jobs_requested_by_id_created_at", table_name="background_jobs")
    op.drop_table("background_jobs")
    op.drop_index("uq_users_username_active", table_name="users", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index("uq_users_email_active", table_name="users", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index("ix_users_role_created", table_name="users", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_index("ix_users_manager_id", table_name="users", postgresql_where=sa.text("manager_id IS NOT NULL"))
    op.drop_index(
        "ix_users_institution_role_created", table_name="users", postgresql_where=sa.text("deleted_at IS NULL")
    )
    op.drop_index("ix_users_created_by_id", table_name="users", postgresql_where=sa.text("created_by_id IS NOT NULL"))
    op.drop_index("ix_users_created_active", table_name="users", postgresql_where=sa.text("deleted_at IS NULL"))
    op.drop_table("users")
    op.drop_index(
        "ix_outbox_events_unpublished", table_name="outbox_events", postgresql_where=sa.text("published_at IS NULL")
    )
    op.drop_table("outbox_events")
    op.drop_index("ix_audit_logs_resource", table_name="audit_logs")
    op.drop_index("ix_audit_logs_institution_id_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
