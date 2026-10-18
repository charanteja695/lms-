"""Handlers for events this service consumes from other services (see lms-backend/README.md
and catalog-service/README.md "Consumes events"). Each handler is idempotent (a plain upsert
of already-known-good values), so at-least-once redelivery from the consumer group is safe.

Payload contracts (owned jointly with the emitting service until it exists):
  media.ready       {"media_asset_id": "<public id>", "kind": "video" | "image" | "document", "duration_seconds": int?}
                    (media-service's payload; every item using that asset becomes ready. The older
                    {"topic_item_id": ...} shape is still accepted.)
  transcript.ready  {"topic_item_id": "<public id>"}
  test.published    {"target_type": "module" | "topic" | "course" | null, "target_id": "<public id>", "test_id": "<public id>", ...}
                    (only module and topic targets are attached; assessment-service's payload carries more fields)
"""

import logging
from typing import Any

from lms_common.events import Event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module import Module
from app.models.topic import Topic
from app.models.topic_item import TopicItem

logger = logging.getLogger(__name__)


async def handle_media_ready(db: AsyncSession, payload: dict[str, Any]) -> None:
    if payload.get("media_asset_id"):
        # Lessons are created with the asset's id before its upload completes, so they exist by the time it's ready.
        media_id = int(payload["media_asset_id"])
        items = (await db.execute(select(TopicItem).where(TopicItem.media_id == media_id))).scalars().all()
    else:
        topic_item_id = int(payload["topic_item_id"])
        items = (await db.execute(select(TopicItem).where(TopicItem.public_id == topic_item_id))).scalars().all()
    if not items:
        logger.info("media.ready for media no lesson uses", extra={"extra_fields": {"payload": payload}})
        return
    for item in items:
        item.media_ready = True
        if payload.get("duration_seconds") is not None:
            item.duration_seconds = int(payload["duration_seconds"])


async def handle_transcript_ready(db: AsyncSession, payload: dict[str, Any]) -> None:
    topic_item_id = int(payload["topic_item_id"])
    item = (await db.execute(select(TopicItem).where(TopicItem.public_id == topic_item_id))).scalar_one_or_none()
    if item is None:
        logger.warning(
            "transcript.ready for an unknown topic item", extra={"extra_fields": {"topic_item_id": topic_item_id}}
        )
        return
    item.transcript_ready = True


async def handle_test_published(db: AsyncSession, payload: dict[str, Any]) -> None:
    target_type = payload.get("target_type")
    if target_type not in ("module", "topic") or not payload.get("target_id"):
        return  # not attachable here: see the note below
    target_id = int(payload["target_id"])
    test_id = int(payload["test_id"])
    if target_type == "module":
        module = (await db.execute(select(Module).where(Module.public_id == target_id))).scalar_one_or_none()
        if module is not None:
            module.module_test_id = test_id
    elif target_type == "topic":
        topic = (await db.execute(select(Topic).where(Topic.public_id == target_id))).scalar_one_or_none()
        if topic is not None:
            topic.topic_test_id = test_id
    # Any other target (assessment-service also publishes a course's final test, practice and hiring tests) is not
    # attached automatically: a final test is chosen on the course rule, and the others have no catalog target.


_HANDLERS = {
    "media.ready": handle_media_ready,
    "transcript.ready": handle_transcript_ready,
    "test.published": handle_test_published,
}


async def dispatch(db: AsyncSession, event: Event) -> None:
    handler = _HANDLERS.get(event.event_type)
    if handler is None:
        return  # not one of ours; the stream is shared by every service
    await handler(db, event.payload)
