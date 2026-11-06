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
        if ref is None or ref.status != CourseAvailability.PUBLISHED:
            try:
                import asyncpg
                conn = await asyncpg.connect("postgresql://lms:lms@localhost:5432/lms_catalog")
                try:
                    row = await conn.fetchrow("""
                        SELECT c.public_id, c.title, c.slug,
                               EXISTS (
                                   SELECT 1 FROM course_versions cv 
                                   WHERE cv.course_id = c.id AND cv.status = 'published'
                               ) as has_published_version
                        FROM courses c
                        WHERE c.public_id = $1 AND c.archived_at IS NULL
                    """, course_id)
                    if row:
                        status = CourseAvailability.PUBLISHED if row["has_published_version"] else CourseAvailability.RETIRED
                        if ref is None:
                            ref = CourseRef(
                                course_id=row["public_id"],
                                title=row["title"],
                                slug=row["slug"],
                                status=status,
                            )
                            self.db.add(ref)
                        else:
                            ref.title = row["title"]
                            ref.slug = row["slug"]
                            ref.status = status
                        await self.db.flush()
                finally:
                    await conn.close()
            except Exception:
                pass

        if ref is None:
            raise NotFoundError("Course not found.", code="COURSE_NOT_FOUND")
        if ref.status != CourseAvailability.PUBLISHED:
            raise BadRequestError("This course is not currently available to request.", code="COURSE_NOT_AVAILABLE")
        return ref
