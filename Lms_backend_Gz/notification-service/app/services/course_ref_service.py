from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course_ref import CourseRef

FALLBACK_TITLE = "your course"  # the course.published event predates this service's first start


class CourseRefService:
    """Course titles for message wording (see app/models/course_ref.py). Read-only outside the consumer."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def upsert(self, payload: dict[str, Any]) -> None:
        version_id = int(payload["version_id"])
        ref = await self.db.get(CourseRef, version_id)
        if ref is None:
            ref = CourseRef(version_id=version_id, course_id=int(payload["course_id"]), title=payload["title"])
            self.db.add(ref)
        ref.title = payload["title"]

    async def title_for_version(self, version_id: int) -> str:
        ref = await self.db.get(CourseRef, version_id)
        return ref.title if ref else FALLBACK_TITLE

    async def title_for_course(self, course_id: int) -> str:
        title = (
            await self.db.execute(
                select(CourseRef.title)
                .where(CourseRef.course_id == course_id)
                .order_by(CourseRef.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return title or FALLBACK_TITLE
