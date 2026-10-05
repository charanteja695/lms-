"""Keeps the local course-structure mirror (app/models/course_version_ref.py and friends) in
sync with catalog-service.

  course.published  full authoring tree — see catalog-service's ReviewService._published_structure_payload
  course.retired     {"course_id": ..., "version_id": ..., "title": ..., "slug": ...}
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.course_structure_service import CourseStructureService


async def handle_course_published(db: AsyncSession, payload: dict[str, Any]) -> None:
    await CourseStructureService(db).upsert_published(payload)


async def handle_course_retired(db: AsyncSession, payload: dict[str, Any]) -> None:
    await CourseStructureService(db).mark_retired(payload)
