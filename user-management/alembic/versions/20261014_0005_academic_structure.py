"""An institution's academic structure: departments, programs, sections; students placed in a section.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-14 09:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("head_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_departments")),
        sa.UniqueConstraint("public_id", name=op.f("uq_departments_public_id")),
    )
    op.create_index("uq_departments_institution_code", "departments", ["institution_id", "code"], unique=True)
    op.create_table(
        "programs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", sa.Uuid(), sa.ForeignKey("departments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("duration_years", sa.SmallInteger(), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_programs")),
        sa.UniqueConstraint("public_id", name=op.f("uq_programs_public_id")),
    )
    op.create_index("uq_programs_institution_code", "programs", ["institution_id", "code"], unique=True)
    op.create_index("ix_programs_department_id", "programs", ["department_id"])
    op.create_table(
        "class_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("public_id", sa.BigInteger(), nullable=False),
        sa.Column("institution_id", sa.Uuid(), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("program_id", sa.Uuid(), sa.ForeignKey("programs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("year_of_study", sa.SmallInteger(), nullable=False),
        sa.Column("name", sa.String(20), nullable=False),
        sa.Column("class_teacher_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_class_sections")),
        sa.UniqueConstraint("public_id", name=op.f("uq_class_sections_public_id")),
    )
    op.create_index("uq_class_sections_program_year_name", "class_sections", ["program_id", "year_of_study", "name"], unique=True)
    op.create_index("ix_class_sections_institution_id", "class_sections", ["institution_id"])
    with op.batch_alter_table("student_profiles") as batch:
        batch.add_column(sa.Column("class_section_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_student_profiles_class_section_id_class_sections", "class_sections", ["class_section_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_student_profiles_class_section_id", ["class_section_id"])


def downgrade() -> None:
    with op.batch_alter_table("student_profiles") as batch:
        batch.drop_index("ix_student_profiles_class_section_id")
        batch.drop_constraint("fk_student_profiles_class_section_id_class_sections", type_="foreignkey")
        batch.drop_column("class_section_id")
    op.drop_table("class_sections")
    op.drop_table("programs")
    op.drop_table("departments")
