from lms_common.pagination import contains_pattern, paginate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.core.ids import new_public_id
from app.db.session import commit_or_conflict, flush_or_conflict
from app.domain.enums import ContentStatus
from app.models.course import Course
from app.models.course_rule import CourseRule
from app.models.course_version import CourseVersion
from app.schemas.course import CourseCreate, CourseListQuery, CourseUpdate

_LOAD_VERSIONS = selectinload(Course.versions)


class CourseService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, actor_user_id: int, data: CourseCreate) -> Course:
        course = Course(
            public_id=new_public_id(),
            title=data.title,
            slug=data.slug,
            summary=data.summary,
            thumbnail_media_id=data.thumbnail_media_id,
            created_by=actor_user_id,
        )
        self.db.add(course)
        await flush_or_conflict(self.db, "A course with this slug already exists")

        version = CourseVersion(
            public_id=new_public_id(),
            course_id=course.id,
            version_number=1,
            status=ContentStatus.DRAFT,
            created_by=actor_user_id,
        )
        self.db.add(version)
        await self.db.flush()
        self.db.add(CourseRule.with_defaults(version.id))
        await commit_or_conflict(self.db)
        return await self.get(course.public_id)

    async def get(self, course_id: int) -> Course:
        course = (
            await self.db.execute(select(Course).where(Course.public_id == course_id).options(_LOAD_VERSIONS))
        ).scalar_one_or_none()
        if course is None:
            raise NotFoundError("Course not found.", code="COURSE_NOT_FOUND")
        return course

    async def list_courses(self, query: CourseListQuery, *, published_only: bool = False) -> tuple[list[Course], int, bool]:
        stmt = select(Course)
        if not query.include_archived:
            stmt = stmt.where(Course.archived_at.is_(None))
        if published_only or query.published_only:
            stmt = stmt.where(Course.versions.any(CourseVersion.status == ContentStatus.PUBLISHED))
        if query.search_text:
            stmt = stmt.where(Course.title.ilike(contains_pattern(query.search_text)))
        stmt = stmt.order_by(Course.created_at.desc() if query.sort_order == "desc" else Course.created_at.asc())
        return await paginate(self.db, stmt, query.page, query.per_page, options=(_LOAD_VERSIONS,))

    async def update(self, course: Course, data: CourseUpdate) -> Course:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(course, field, value)
        await commit_or_conflict(self.db, "A course with this slug already exists")
        try:
            import asyncpg
            conn = await asyncpg.connect("postgresql://lms:lms@127.0.0.1:5432/lms_subscription")
            try:
                await conn.execute(
                    "UPDATE course_refs SET title = $1, slug = $2, updated_at = NOW() WHERE course_id = $3",
                    course.title, course.slug, course.public_id
                )
            finally:
                await conn.close()

            conn_ln = await asyncpg.connect("postgresql://lms:lms@127.0.0.1:5432/lms_learning")
            try:
                await conn_ln.execute(
                    "UPDATE course_version_refs SET title = $1, slug = $2, updated_at = NOW() WHERE course_id = $3",
                    course.title, course.slug, course.public_id
                )
            finally:
                await conn_ln.close()
        except Exception:
            pass
        return course

    async def delete(self, course: Course) -> None:
        from app.core.time import utcnow
        course.archived_at = utcnow()
        await self.db.commit()
