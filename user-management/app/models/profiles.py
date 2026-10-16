import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, SmallInteger, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserProfile(TimestampMixin, Base):
    """Personal details and address. Exactly one row per user."""

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    gender: Mapped[str | None] = mapped_column(String(20))
    date_of_birth: Mapped[date | None]
    alternate_phone: Mapped[str | None] = mapped_column(String(20))
    preferred_language: Mapped[str] = mapped_column(String(10))
    timezone: Mapped[str] = mapped_column(String(64))

    address_line1: Mapped[str | None] = mapped_column(String(255))
    address_line2: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(12))
    country: Mapped[str | None] = mapped_column(String(2))

    user: Mapped["User"] = relationship(back_populates="profile", lazy="raise")

    @property
    def has_address(self) -> bool:
        return self.address_line1 is not None


class EmploymentProfile(TimestampMixin, Base):
    """Employment details for admins, institution heads and staff."""

    __tablename__ = "employment_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # Copy of users.institution_id so employee codes can be unique per institution at the database level.
    institution_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("institutions.id", ondelete="RESTRICT"))
    employee_code: Mapped[str | None] = mapped_column(String(30))
    designation: Mapped[str | None] = mapped_column(String(100))
    department: Mapped[str | None] = mapped_column(String(100))
    employment_type: Mapped[str | None] = mapped_column(String(20))
    date_of_joining: Mapped[date | None]

    user: Mapped["User"] = relationship(back_populates="employment", lazy="raise")

    __table_args__ = (
        Index(
            "ix_employment_profiles_employee_code_trgm",
            "employee_code",
            postgresql_using="gin",
            postgresql_ops={"employee_code": "gin_trgm_ops"},
        ),
        # Codes are never reused inside an institution, even after the employee is deleted.
        Index(
            "uq_employment_profiles_institution_employee_code",
            "institution_id",
            "employee_code",
            unique=True,
            postgresql_where=text("employee_code IS NOT NULL"),
            sqlite_where=text("employee_code IS NOT NULL"),
        ),
    )


class StudentProfile(TimestampMixin, Base):
    __tablename__ = "student_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id", ondelete="RESTRICT"))
    admission_number: Mapped[str] = mapped_column(String(30))
    admission_date: Mapped[date | None]
    # Academic placement: used for batches, reports and job eligibility.
    program: Mapped[str | None] = mapped_column(String(100))  # e.g. B.Tech, Class 10
    branch: Mapped[str | None] = mapped_column(String(100))  # e.g. Computer Science
    year_of_study: Mapped[int | None] = mapped_column(SmallInteger)
    section: Mapped[str | None] = mapped_column(String(20))
    # the section in the institution's academic structure (app/models/academics.py); fills the four fields above
    class_section_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("class_sections.id", ondelete="SET NULL"))
    graduation_year: Mapped[int | None] = mapped_column(SmallInteger)
    cgpa: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))

    user: Mapped["User"] = relationship(back_populates="student", lazy="raise")

    __table_args__ = (
        # Admission numbers are never reused inside an institution, even after the student is deleted.
        UniqueConstraint("institution_id", "admission_number"),
        Index("ix_student_profiles_institution_graduation_branch", "institution_id", "graduation_year", "branch"),
        Index("ix_student_profiles_class_section_id", "class_section_id"),
        Index(
            "ix_student_profiles_admission_number_trgm",
            "admission_number",
            postgresql_using="gin",
            postgresql_ops={"admission_number": "gin_trgm_ops"},
        ),
    )


class StudentGuardian(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "student_guardians"

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    position: Mapped[int]  # display order as submitted
    full_name: Mapped[str] = mapped_column(String(100))
    relationship_type: Mapped[str] = mapped_column("relationship", String(20))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    occupation: Mapped[str | None] = mapped_column(String(100))
    is_primary: Mapped[bool]

    student: Mapped["User"] = relationship(back_populates="guardians", lazy="raise")

    __table_args__ = (Index("ix_student_guardians_student_id", "student_id"),)
