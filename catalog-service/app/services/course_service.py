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
        try:
            import asyncpg
            conn = await asyncpg.connect("postgresql://lms:lms@127.0.0.1:5432/lms_subscription")
            try:
                await conn.execute(
                    "UPDATE course_refs SET status = 'retired', updated_at = NOW() WHERE course_id = $1",
                    course.public_id
                )
            finally:
                await conn.close()
        except Exception:
            pass

    async def bulk_delete(self, course_ids: list[int] | None = None, clear_all_active: bool = False) -> tuple[int, list[str]]:
        from app.core.time import utcnow
        from sqlalchemy import select
        stmt = select(Course).where(Course.archived_at.is_(None))
        if not clear_all_active:
            if not course_ids:
                return 0, []
            stmt = stmt.where(Course.public_id.in_(course_ids))

        result = await self.db.execute(stmt)
        courses = list(result.scalars().all())
        if not courses:
            return 0, []

        now = utcnow()
        deleted_titles = []
        public_ids = []
        for c in courses:
            c.archived_at = now
            deleted_titles.append(f"{c.title} ({c.public_id})")
            public_ids.append(c.public_id)

        await self.db.commit()

        try:
            import asyncpg
            conn = await asyncpg.connect("postgresql://lms:lms@127.0.0.1:5432/lms_subscription")
            try:
                await conn.execute(
                    "UPDATE course_refs SET status = 'retired', updated_at = NOW() WHERE course_id = ANY($1::bigint[])",
                    public_ids
                )
            finally:
                await conn.close()
        except Exception:
            pass

        return len(courses), deleted_titles

    async def get_cleanup_summary(self) -> dict[str, int]:
        from app.models.module import Module
        from app.models.topic import Topic
        from sqlalchemy import func, distinct

        active_count = (await self.db.execute(
            select(func.count(Course.id)).where(Course.archived_at.is_(None))
        )).scalar() or 0

        published_count = (await self.db.execute(
            select(func.count(distinct(Course.id)))
            .join(CourseVersion, CourseVersion.course_id == Course.id)
            .where(Course.archived_at.is_(None), CourseVersion.status == ContentStatus.PUBLISHED)
        )).scalar() or 0

        draft_count = active_count - published_count

        modules_count = (await self.db.execute(
            select(func.count(Module.id))
            .join(CourseVersion, Module.course_version_id == CourseVersion.id)
            .join(Course, CourseVersion.course_id == Course.id)
            .where(Course.archived_at.is_(None))
        )).scalar() or 0

        chapters_count = (await self.db.execute(
            select(func.count(Topic.id))
            .join(Module, Topic.module_id == Module.id)
            .join(CourseVersion, Module.course_version_id == CourseVersion.id)
            .join(Course, CourseVersion.course_id == Course.id)
            .where(Course.archived_at.is_(None))
        )).scalar() or 0

        return {
            "active_courses_count": active_count,
            "published_courses_count": published_count,
            "draft_courses_count": draft_count,
            "total_modules_count": modules_count,
            "total_chapters_count": chapters_count,
        }
