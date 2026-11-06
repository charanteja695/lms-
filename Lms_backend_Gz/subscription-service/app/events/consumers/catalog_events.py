"""Keeps app/models/course_ref.py in sync with catalog-service's courses.

  course.published  {"course_id": "<public id>", "version_id": "<public id>", "title": ..., "slug": ...}
  course.retired     {"course_id": "<public id>", "version_id": "<public id>", "title": ..., "slug": ...}
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import CourseAvailability
from app.services.course_ref_service import CourseRefService


async def handle_course_published(db: AsyncSession, payload: dict[str, Any]) -> None:
    await CourseRefService(db).upsert(payload, status=CourseAvailability.PUBLISHED)


async def handle_course_retired(db: AsyncSession, payload: dict[str, Any]) -> None:
    await CourseRefService(db).upsert(payload, status=CourseAvailability.RETIRED)
