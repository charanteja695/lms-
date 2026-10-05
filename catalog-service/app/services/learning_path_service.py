from lms_common.pagination import contains_pattern, paginate
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.ids import new_public_id
from app.core.time import utcnow
from app.db.session import commit_or_conflict, flush_or_conflict
from app.domain.enums import ContentStatus
from app.models.course import Course
from app.models.learning_path import LearningPath
from app.models.learning_path_item import LearningPathItem
from app.schemas.common import ListQuery
from app.schemas.learning_path import LearningPathCreate, LearningPathUpdate

_LOAD_ITEMS = selectinload(LearningPath.items).selectinload(LearningPathItem.course)


class LearningPathService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, actor_user_id: int, data: LearningPathCreate) -> LearningPath:
        path = LearningPath(
            public_id=new_public_id(),
            title=data.title,
            slug=data.slug,
            description=data.description,
            created_by=actor_user_id,
        )
        self.db.add(path)
        await commit_or_conflict(self.db, "A learning path with this slug already exists")
        return await self.get(path.public_id)

    async def get(self, learning_path_id: int) -> LearningPath:
        # populate_existing: callers re-fetch after mutating items (add/remove/reorder) within the
        # same request session, where the identity map would otherwise keep the stale collection order.
        path = (
            await self.db.execute(
                select(LearningPath)
                .where(LearningPath.public_id == learning_path_id)
                .options(_LOAD_ITEMS)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if path is None:
            raise NotFoundError("Learning path not found.", code="LEARNING_PATH_NOT_FOUND")
        return path

    async def list_learning_paths(self, query: ListQuery) -> tuple[list[LearningPath], int, bool]:
        stmt = select(LearningPath)
        if query.search_text:
            stmt = stmt.where(LearningPath.title.ilike(contains_pattern(query.search_text)))
        stmt = stmt.order_by(
            LearningPath.created_at.desc() if query.sort_order == "desc" else LearningPath.created_at.asc()
        )
        return await paginate(self.db, stmt, query.page, query.per_page, options=(_LOAD_ITEMS,))

    async def update(self, path: LearningPath, data: LearningPathUpdate) -> LearningPath:
        self._ensure_draft(path)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(path, field, value)
        await commit_or_conflict(self.db)
        return path

    async def add_course(self, path: LearningPath, course_public_id: int) -> LearningPath:
        self._ensure_draft(path)
        course = (
            await self.db.execute(select(Course).where(Course.public_id == course_public_id))
        ).scalar_one_or_none()
        if course is None:
            raise NotFoundError("Course not found.", code="COURSE_NOT_FOUND")

        next_position = (
            await self.db.execute(select(func.max(LearningPathItem.position)).where(LearningPathItem.learning_path_id == path.id))
        ).scalar_one()
        self.db.add(LearningPathItem(learning_path_id=path.id, course_id=course.id, position=(next_position or 0) + 1))
        await flush_or_conflict(self.db, "This course is already in the learning path")
        await self.db.commit()
        return await self.get(path.public_id)

    async def remove_course(self, path: LearningPath, course_public_id: int) -> LearningPath:
        self._ensure_draft(path)
        item = (
            await self.db.execute(
                select(LearningPathItem)
                .join(Course)
                .where(LearningPathItem.learning_path_id == path.id, Course.public_id == course_public_id)
            )
        ).scalar_one_or_none()
        if item is None:
            raise NotFoundError("This course is not in the learning path.", code="LEARNING_PATH_ITEM_NOT_FOUND")
        await self.db.delete(item)
        await self.db.commit()
        return await self.get(path.public_id)

    async def reorder(self, path: LearningPath, ordered_course_ids: list[int]) -> LearningPath:
        self._ensure_draft(path)
        rows = list(
            (
                await self.db.execute(
                    select(LearningPathItem, Course.public_id)
                    .join(Course)
                    .where(LearningPathItem.learning_path_id == path.id, Course.public_id.in_(ordered_course_ids))
                )
            ).all()
        )
        by_course_id = {course_public_id: item for item, course_public_id in rows}
        if set(by_course_id) != set(ordered_course_ids):
            raise NotFoundError("One or more courses are not in this learning path.", code="LEARNING_PATH_ITEM_NOT_FOUND")
        for position, course_id in enumerate(ordered_course_ids, start=1):
            by_course_id[course_id].position = position
        await self.db.commit()
        return await self.get(path.public_id)

    async def publish(self, path: LearningPath) -> LearningPath:
        self._ensure_draft(path)
        if not path.items:
            raise BadRequestError("Add at least one course before publishing.", code="EMPTY_LEARNING_PATH")
        path.status = ContentStatus.PUBLISHED
        path.published_at = utcnow()
        await self.db.commit()
        return path

    async def archive(self, path: LearningPath) -> LearningPath:
        if path.status != ContentStatus.PUBLISHED:
            raise BadRequestError("Only a published learning path can be archived.", code="LEARNING_PATH_NOT_PUBLISHED")
        path.status = ContentStatus.ARCHIVED
        path.archived_at = utcnow()
        await self.db.commit()
        return path

    def _ensure_draft(self, path: LearningPath) -> None:
        if path.status != ContentStatus.DRAFT:
            raise ConflictError("This learning path is no longer a draft.", code="LEARNING_PATH_NOT_DRAFT")
