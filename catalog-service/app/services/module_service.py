import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
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
            position=next_position,
            pass_mark=data.pass_mark,
        )
        self.db.add(module)
        await commit_or_conflict(self.db)
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
        return module

    async def delete(self, module: Module) -> None:
        await self.db.delete(module)
        await self.db.commit()

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

    async def _next_position(self, course_version_id: uuid.UUID) -> int:
        current_max = (
            await self.db.execute(select(func.max(Module.position)).where(Module.course_version_id == course_version_id))
        ).scalar_one()
        return (current_max or 0) + 1
