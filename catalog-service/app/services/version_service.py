import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.ids import new_public_id
from app.db.session import commit_or_conflict
from app.domain.enums import ContentStatus
from app.models.course import Course
from app.models.course_rule import CourseRule
from app.models.course_version import CourseVersion
from app.models.module import Module
from app.models.topic import Topic

_NON_TERMINAL = (ContentStatus.DRAFT, ContentStatus.IN_REVIEW)

_LOAD_DETAIL = (
    selectinload(CourseVersion.rule),
    selectinload(CourseVersion.modules).selectinload(Module.topics).selectinload(Topic.items),
)


class VersionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_draft(self, course: Course, actor_user_id: int) -> CourseVersion:
        existing = (
            await self.db.execute(
                select(CourseVersion.id).where(
                    CourseVersion.course_id == course.id, CourseVersion.status.in_(_NON_TERMINAL)
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(
                "This course already has a draft or in-review version. Finish or reject it first.",
                code="DRAFT_ALREADY_EXISTS",
            )

        next_number = (
            await self.db.execute(select(func.max(CourseVersion.version_number)).where(CourseVersion.course_id == course.id))
        ).scalar_one()
        version = CourseVersion(
            public_id=new_public_id(),
            course_id=course.id,
            version_number=(next_number or 0) + 1,
            status=ContentStatus.DRAFT,
            created_by=actor_user_id,
        )
        self.db.add(version)
        await self.db.flush()
        self.db.add(CourseRule.with_defaults(version.id))
        await commit_or_conflict(self.db)
        return version

    async def get(self, course_id: uuid.UUID | int, version_id: int) -> CourseVersion:
        stmt = select(CourseVersion).where(CourseVersion.public_id == version_id)
        stmt = stmt.join(Course).where(Course.public_id == course_id) if isinstance(course_id, int) else stmt.where(
            CourseVersion.course_id == course_id
        )
        version = (await self.db.execute(stmt)).scalar_one_or_none()
        if version is None:
            raise NotFoundError("Course version not found.", code="COURSE_VERSION_NOT_FOUND")
        return version

    async def get_detail(self, course_id: int, version_id: int) -> CourseVersion:
        version = (
            await self.db.execute(
                select(CourseVersion)
                .join(Course)
                .where(Course.public_id == course_id, CourseVersion.public_id == version_id)
                .options(*_LOAD_DETAIL)
            )
        ).scalar_one_or_none()
        if version is None:
            raise NotFoundError("Course version not found.", code="COURSE_VERSION_NOT_FOUND")
        return version

    def ensure_draft(self, version: CourseVersion) -> None:
        if version.status not in (ContentStatus.DRAFT, ContentStatus.PUBLISHED):
            raise BadRequestError(
                "This course version cannot be edited.", code="VERSION_NOT_EDITABLE"
            )
