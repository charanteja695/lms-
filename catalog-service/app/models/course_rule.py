import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import UnlockMode

if TYPE_CHECKING:
    from app.models.course_version import CourseVersion


class CourseRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-version overrides of the platform defaults in Settings (docs/PRODUCT.md §3.1).
    One row per course version, created with defaults when the version is created."""

    __tablename__ = "course_rules"

    course_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_versions.id", ondelete="CASCADE"), unique=True
    )
    unlock_mode: Mapped[str] = mapped_column(String(20), default=UnlockMode.SEQUENTIAL, server_default=UnlockMode.SEQUENTIAL)
    final_test_id: Mapped[int | None] = mapped_column(BigInteger, doc="test owned by assessment-service")
    final_pass_mark: Mapped[int]
    final_test_attempts: Mapped[int]
    final_test_cooldown_days: Mapped[int]

    course_version: Mapped["CourseVersion"] = relationship(back_populates="rule", lazy="raise")

    @classmethod
    def with_defaults(cls, course_version_id: uuid.UUID) -> "CourseRule":
        from app.core.config import get_settings

        settings = get_settings()
        return cls(
            course_version_id=course_version_id,
            final_pass_mark=settings.DEFAULT_FINAL_PASS_MARK,
            final_test_attempts=settings.DEFAULT_FINAL_TEST_ATTEMPTS,
            final_test_cooldown_days=settings.DEFAULT_FINAL_TEST_COOLDOWN_DAYS,
        )
