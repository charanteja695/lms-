"""Composite dependencies shared by the module/topic/topic-item authoring endpoints:
resolve the course version and confirm it is still a draft before any structural edit."""

from typing import Annotated

from fastapi import Depends

from app.api.deps import CourseIdParam, DbSession, ModuleIdParam, TopicIdParam, TopicItemIdParam, VersionIdParam
from app.models.course_version import CourseVersion
from app.models.module import Module
from app.models.topic import Topic
from app.models.topic_item import TopicItem
from app.services.module_service import ModuleService
from app.services.topic_item_service import TopicItemService
from app.services.topic_service import TopicService
from app.services.version_service import VersionService


async def draft_version(db: DbSession, course_id: CourseIdParam, version_id: VersionIdParam) -> CourseVersion:
    service = VersionService(db)
    version = await service.get(course_id, version_id)
    service.ensure_draft(version)
    return version


DraftVersion = Annotated[CourseVersion, Depends(draft_version)]


async def module_in_version(db: DbSession, version: DraftVersion, module_id: ModuleIdParam) -> Module:
    return await ModuleService(db).get(version, module_id)


ModuleInVersion = Annotated[Module, Depends(module_in_version)]


async def topic_in_module(db: DbSession, module: ModuleInVersion, topic_id: TopicIdParam) -> Topic:
    return await TopicService(db).get(module, topic_id)


TopicInModule = Annotated[Topic, Depends(topic_in_module)]


async def item_in_topic(db: DbSession, topic: TopicInModule, topic_item_id: TopicItemIdParam) -> TopicItem:
    return await TopicItemService(db).get(topic, topic_item_id)


ItemInTopic = Annotated[TopicItem, Depends(item_in_topic)]
