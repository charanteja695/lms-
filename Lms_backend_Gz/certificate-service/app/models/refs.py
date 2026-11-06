"""Read-models from other services' events (a service never reads another's tables). They only supply the words
printed on a certificate: who, where, what course."""

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class UserRef(TimestampMixin, Base):
    """From user-management's ``user.*`` events. Kept after a user is deleted: a certificate must still verify."""

    __tablename__ = "user_refs"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    organization_id: Mapped[int | None] = mapped_column(BigInteger)


class InstitutionRef(TimestampMixin, Base):
    """From user-management's ``institution.*`` events."""

    __tablename__ = "institution_refs"

    organization_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200))


class CourseRef(TimestampMixin, Base):
    """From catalog-service's ``course.published`` (the latest title wins)."""

    __tablename__ = "course_refs"

    course_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(200))
