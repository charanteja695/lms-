from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.domain.enums import CourseVersionStatus, UnlockMode

if TYPE_CHECKING:
    from app.models.module_ref import ModuleRef


class CourseVersionRef(TimestampMixin, Base):
    """Local mirror of one catalog-service published course version — modules, topics and
    items included (see app/events/consumers/catalog_events.py). Built entirely from the
    ``course.published`` event payload, which carries the full authoring tree for exactly this
    reason (see catalog-service's ``ReviewService._published_structure_payload``); this service
    never calls catalog-service back.

    Keyed by ``version_id`` (not ``course_id``): a batch is created against one immutable
    published version and keeps using it even after a newer version publishes (see
    docs/PRODUCT.md §3.2 "subscriptions choose upgrade policy").
    """

    __tablename__ = "course_version_refs"

    version_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    course_id: Mapped[int] = mapped_column(BigInteger, index=True)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220))
    status: Mapped[str] = mapped_column(String(20), default=CourseVersionStatus.PUBLISHED, server_default=CourseVersionStatus.PUBLISHED)
    unlock_mode: Mapped[str] = mapped_column(String(20), default=UnlockMode.SEQUENTIAL, server_default=UnlockMode.SEQUENTIAL)
    final_test_id: Mapped[int | None] = mapped_column(BigInteger)
    final_pass_mark: Mapped[int]
    final_test_attempts: Mapped[int]
    final_test_cooldown_days: Mapped[int]

    modules: Mapped[list["ModuleRef"]] = relationship(
        back_populates="course_version", order_by="ModuleRef.position", lazy="raise"
    )
