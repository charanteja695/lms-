import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.domain.enums import ContentStatus
from app.services.review_service import ReviewService
from app.core.ids import new_public_id
from app.db.session import commit_or_conflict
from app.models.course_version import CourseVersion
from app.models.module import Module
from app.schemas.module import ModuleCreate, ModuleUpdate


class ModuleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, version: CourseVersion, data: ModuleCreate) -> Module:
        next_position = await self._next_position(version.id)
        module = Module(
            public_id=new_public_id(),
            course_version_id=version.id,
            title=data.title,
            description=data.description,
            position=next_position,
            pass_mark=data.pass_mark,
        )
        self.db.add(module)
        await commit_or_conflict(self.db)
        if version.status == ContentStatus.PUBLISHED:
            await ReviewService(self.db).sync_published_curriculum(version)
        return module

    async def get(self, version: CourseVersion, module_id: int) -> Module:
        module = (
            await self.db.execute(
                select(Module).where(Module.course_version_id == version.id, Module.public_id == module_id)
            )
        ).scalar_one_or_none()
        if module is None:
            raise NotFoundError("Module not found.", code="MODULE_NOT_FOUND")
        return module

    async def update(self, module: Module, data: ModuleUpdate) -> Module:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(module, field, value)
        await commit_or_conflict(self.db)
        version = (
            await self.db.execute(select(CourseVersion).where(CourseVersion.id == module.course_version_id))
        ).scalar_one_or_none()
        if version and version.status == ContentStatus.PUBLISHED:
            await ReviewService(self.db).sync_published_curriculum(version)
        return module

    async def delete(self, module: Module) -> None:
        try:
            import asyncpg
            conn = await asyncpg.connect("postgresql://lms:lms@127.0.0.1:5432/lms_learning")
            try:
                prog_count = await conn.fetchval('''
                    SELECT COUNT(*) FROM item_progress ip
                    JOIN topic_item_refs tir ON ip.topic_item_id = tir.topic_item_id
                    JOIN topic_refs tr ON tir.topic_id = tr.topic_id
                    WHERE tr.module_id = $1
                ''', module.public_id)
                res_count = 0
                if module.module_test_id:
                    res_count = await conn.fetchval('''
                        SELECT COUNT(*) FROM assessment_results WHERE test_id = $1
                    ''', module.module_test_id)
                if (prog_count or 0) > 0 or (res_count or 0) > 0:
                    raise BadRequestError(
                        "Cannot delete module because student progress or assessment records exist for it.",
                        code="STUDENT_PROGRESS_EXISTS"
                    )
                await conn.execute('''
                    DELETE FROM topic_item_refs WHERE topic_id IN (SELECT topic_id FROM topic_refs WHERE module_id = $1);
                    DELETE FROM topic_refs WHERE module_id = $1;
                    DELETE FROM module_refs WHERE module_id = $1;
                ''', module.public_id)
            finally:
                await conn.close()
        except BadRequestError:
            raise
        except Exception:
            pass

        version = (
            await self.db.execute(select(CourseVersion).where(CourseVersion.id == module.course_version_id))
        ).scalar_one_or_none()
        await self.db.delete(module)
        await self.db.commit()
        if version and version.status == ContentStatus.PUBLISHED:
            await ReviewService(self.db).sync_published_curriculum(version)

    async def reorder(self, version: CourseVersion, ordered_module_ids: list[int]) -> None:
        modules = list(
            (
                await self.db.execute(
                    select(Module).where(Module.course_version_id == version.id, Module.public_id.in_(ordered_module_ids))
                )
            )
            .scalars()
            .all()
        )
        by_public_id = {module.public_id: module for module in modules}
        if len(by_public_id) != len(ordered_module_ids) or set(by_public_id) != set(ordered_module_ids):
            raise NotFoundError("One or more modules were not found in this course version.", code="MODULE_NOT_FOUND")
        for position, module_id in enumerate(ordered_module_ids, start=1):
            by_public_id[module_id].position = position
        await self.db.commit()
        if version.status == ContentStatus.PUBLISHED:
            await ReviewService(self.db).sync_published_curriculum(version)

    async def _next_position(self, course_version_id: uuid.UUID) -> int:
        current_max = (
            await self.db.execute(select(func.max(Module.position)).where(Module.course_version_id == course_version_id))
        ).scalar_one()
        return (current_max or 0) + 1
