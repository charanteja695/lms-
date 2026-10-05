from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.domain.enums import CourseAvailability
from app.models.course_ref import CourseRef


class CourseRefService:
    """Local read-model of catalog-service's courses (see app/models/course_ref.py). Only the
    event consumer writes to it; callers only ever read."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert(self, payload: dict[str, Any], *, status: CourseAvailability) -> None:
        course_id = int(payload["course_id"])
        ref = await self.db.get(CourseRef, course_id)
        if ref is None:
            ref = CourseRef(course_id=course_id, title=payload["title"], slug=payload["slug"], status=status)
            self.db.add(ref)
        else:
            ref.title = payload["title"]
            ref.slug = payload["slug"]
            ref.status = status

    async def get_requestable(self, course_id: int) -> CourseRef:
        ref = await self.db.get(CourseRef, course_id)
        if ref is None:
            raise NotFoundError("Course not found.", code="COURSE_NOT_FOUND")
        if ref.status != CourseAvailability.PUBLISHED:
            raise BadRequestError("This course is not currently available to request.", code="COURSE_NOT_AVAILABLE")
        return ref
