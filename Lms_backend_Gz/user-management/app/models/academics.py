"""An institution's academic structure: departments -> programs -> sections, with students placed in a section.

Institute head (and the owning admin, and the super admin) keeps it; staff read it. A department may name its head
(HOD), one of the institution's staff. Placing a student in a section also fills the student's program / branch /
year / section text, so everything that already reads those fields keeps working.
"""

import uuid

from sqlalchemy import BigInteger, ForeignKey, Index, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import new_public_id
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Department(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "departments"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, default=new_public_id)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))  # e.g. Computer Science and Engineering
    code: Mapped[str] = mapped_column(String(20))  # e.g. CSE, unique within the institution (upper-cased)
    head_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))  # HOD

    __table_args__ = (Index("uq_departments_institution_code", "institution_id", "code", unique=True),)


class Program(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "programs"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, default=new_public_id)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"))
    department_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("departments.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(120))  # e.g. B.Tech Computer Science
    code: Mapped[str] = mapped_column(String(20))  # unique within the institution
    duration_years: Mapped[int] = mapped_column(SmallInteger)

    __table_args__ = (
        Index("uq_programs_institution_code", "institution_id", "code", unique=True),
        Index("ix_programs_department_id", "department_id"),
    )


class ClassSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A class of students in one year of a program, e.g. B.Tech CSE, year 2, section A."""

    __tablename__ = "class_sections"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True, default=new_public_id)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id", ondelete="CASCADE"))
    program_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programs.id", ondelete="RESTRICT"))
    year_of_study: Mapped[int] = mapped_column(SmallInteger)
    name: Mapped[str] = mapped_column(String(20))  # e.g. A
    class_teacher_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    __table_args__ = (
        Index("uq_class_sections_program_year_name", "program_id", "year_of_study", "name", unique=True),
        Index("ix_class_sections_institution_id", "institution_id"),
    )
