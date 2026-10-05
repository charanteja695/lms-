"""Keeps the local read-models in sync (see app/models/user_ref.py and course_ref.py).

  user.created / user.updated / user.suspended / user.activated
      {"user_id": "<public id>", "email": ..., "first_name": ..., "role": ..., "status": ...,
       "organization_id": "<public id>" | null, ...}
  user.deleted
      the same payload; the directory keeps the row with status "deleted"
  course.published
      {"course_id": "<public id>", "version_id": "<public id>", "title": ..., ...}
"""

from lms_common.events import Event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services.course_ref_service import CourseRefService
from app.services.user_ref_service import UserRefService


async def handle_user_upserted(db: AsyncSession, event: Event, settings: Settings) -> None:
    await UserRefService(db).upsert(event.payload)


async def handle_user_deleted(db: AsyncSession, event: Event, settings: Settings) -> None:
    await UserRefService(db).mark_deleted(int(str(event.payload["user_id"])))


async def handle_course_published(db: AsyncSession, event: Event, settings: Settings) -> None:
    await CourseRefService(db).upsert(event.payload)
