"""Building the course-content index from catalog-service's ``course.published`` (and, once media-service emits it,
``transcript.ready``).

Two steps with a hard line between them: the event handler *chunks* (cheap, no I/O beyond the database, so it runs inside
the consumer's transaction and an event is either fully applied or not at all), and a worker job *embeds* the chunks that
still have no vector (a slow external call, made outside any transaction, lease-claimed so a dying worker loses nothing).
Until a chunk is embedded it is still found by the lexical fallback, so a slow or failing gateway never leaves a freshly
published course unanswerable.
"""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients.gateway import GatewayClient, GatewayError
from app.core.config import Settings
from app.core.time import utcnow
from app.domain.enums import JobStatus
from app.models.content import ContentChunk, IndexJob
from app.models.refs import CourseVersionRef, ItemRef
from app.rag.chunker import chunk_text, window_transcript

logger = logging.getLogger(__name__)

_TEXT_ITEM_TYPES = {"notes", "practice"}


def embedding_text(chunk: ContentChunk) -> str:
    """What is embedded: the lesson's place in the course, then the passage — a bare paragraph loses "this is about
    recursion in the Python module"."""
    return f"{chunk.module_title} > {chunk.topic_title} > {chunk.item_title}\n{chunk.text}".strip()


class IndexService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def _schedule(self, version_id: int) -> None:
        job = (await self.db.execute(select(IndexJob).where(IndexJob.version_id == version_id).with_for_update())).scalar_one_or_none()
        if job is None:
            self.db.add(IndexJob(version_id=version_id, status=JobStatus.PENDING))
        else:
            job.status, job.attempts, job.next_attempt_at, job.lease_until, job.last_error = JobStatus.PENDING, 0, None, None, None

    # ------------------------------------------------------------------ events

    async def on_course_published(self, payload: dict[str, Any]) -> None:
        version_id, course_id = int(payload["version_id"]), int(payload["course_id"])
        ref = await self.db.get(CourseVersionRef, version_id)
        if ref is None:
            ref = CourseVersionRef(version_id=version_id, course_id=course_id, title="")
            self.db.add(ref)
        ref.course_id, ref.title, ref.slug, ref.retired = course_id, payload.get("title") or ref.title, payload.get("slug") or "", False

        await self.db.execute(delete(ContentChunk).where(ContentChunk.version_id == version_id, ContentChunk.source == "item"))
        for module in payload.get("modules", []):
            for topic in module.get("topics", []):
                for item in topic.get("items", []):
                    item_id = int(item["topic_item_id"])
                    item_ref = await self.db.get(ItemRef, item_id)
                    if item_ref is None:
                        item_ref = ItemRef(item_id=item_id, version_id=version_id, course_id=course_id, item_type=item["item_type"])
                        self.db.add(item_ref)
                    item_ref.module_title, item_ref.topic_title = module.get("title", ""), topic.get("title", "")
                    item_ref.title, item_ref.item_type, item_ref.position = item.get("title", ""), item["item_type"], int(item.get("position", 0))
                    item_ref.media_id = int(item["media_id"]) if item.get("media_id") else None
                    text = item.get("content_text") or ""
                    if item["item_type"] in _TEXT_ITEM_TYPES and text.strip():
                        for index, passage in enumerate(chunk_text(text, self.settings.CHUNK_MAX_CHARS)):
                            self.db.add(
                                ContentChunk(
                                    version_id=version_id, course_id=course_id, item_id=item_id, source="item", chunk_index=index, text=passage,
                                    module_title=item_ref.module_title, topic_title=item_ref.topic_title, item_title=item_ref.title, item_type=item_ref.item_type,
                                )
                            )
        await self.db.flush()
        await self._schedule(version_id)

    async def on_course_retired(self, payload: dict[str, Any]) -> None:
        version_id = int(payload["version_id"])
        ref = await self.db.get(CourseVersionRef, version_id)
        if ref is not None:
            ref.retired = True
        await self.db.execute(update(ContentChunk).where(ContentChunk.version_id == version_id).values(retired=True))

    async def on_transcript_ready(self, payload: dict[str, Any]) -> None:
        """``{"media_asset_id", "language", "segments": [{"start", "end", "text"}, ...]}`` — the contract media-service
        will emit (it has no transcripts yet). Applies to every item, in every version, that plays that clip."""
        media_id = int(payload.get("media_asset_id") or payload["media_id"])
        segments = [(float(s["start"]), float(s["end"]), str(s["text"])) for s in payload.get("segments", [])]
        windows = window_transcript(segments, self.settings.TRANSCRIPT_WINDOW_SECONDS, self.settings.CHUNK_MAX_CHARS)
        versions: set[int] = set()
        for item in (await self.db.execute(select(ItemRef).where(ItemRef.media_id == media_id))).scalars():
            versions.add(item.version_id)
            await self.db.execute(delete(ContentChunk).where(ContentChunk.item_id == item.item_id, ContentChunk.source == "transcript"))
            for index, window in enumerate(windows):
                self.db.add(
                    ContentChunk(
                        version_id=item.version_id, course_id=item.course_id, item_id=item.item_id, source="transcript", chunk_index=index, text=window.text,
                        start_seconds=window.start, end_seconds=window.end, module_title=item.module_title, topic_title=item.topic_title,
                        item_title=item.title, item_type=item.item_type,
                    )
                )
        await self.db.flush()
        for version_id in versions:
            await self._schedule(version_id)

    # ------------------------------------------------------------------ admin

    async def reindex(self, version_id: int) -> None:
        """Forget every vector of a version and embed it again (an embedding model change)."""
        await self.db.execute(update(ContentChunk).where(ContentChunk.version_id == version_id).values(embedding=None, embedding_model=None))
        await self._schedule(version_id)
        await self.db.commit()

    async def status(self, course_id: int) -> list[dict[str, Any]]:
        out = []
        for ref in (await self.db.execute(select(CourseVersionRef).where(CourseVersionRef.course_id == course_id).order_by(CourseVersionRef.created_at))).scalars():
            total, embedded = (
                await self.db.execute(
                    select(func.count(ContentChunk.id), func.count(ContentChunk.embedding)).where(ContentChunk.version_id == ref.version_id, ContentChunk.retired.is_(False))
                )
            ).one()
            job = (await self.db.execute(select(IndexJob).where(IndexJob.version_id == ref.version_id))).scalar_one_or_none()
            out.append(
                {
                    "version_id": ref.version_id, "retired": ref.retired, "chunks": int(total), "embedded_chunks": int(embedded),
                    "job_status": job.status if job else None, "job_attempts": job.attempts if job else 0, "last_error": job.last_error if job else None,
                }
            )
        return out

    # ------------------------------------------------------------------ worker

    async def claim(self, limit: int) -> list[Any]:
        now = utcnow()
        due = or_(and_(IndexJob.status == JobStatus.PENDING, or_(IndexJob.next_attempt_at.is_(None), IndexJob.next_attempt_at <= now)), and_(IndexJob.status == JobStatus.RUNNING, IndexJob.lease_until < now))
        jobs = (await self.db.execute(select(IndexJob).where(due).order_by(IndexJob.created_at).limit(limit).with_for_update(skip_locked=True))).scalars().all()
        for job in jobs:
            job.status, job.lease_until, job.attempts = JobStatus.RUNNING, now + timedelta(seconds=self.settings.INDEX_LEASE_SECONDS), job.attempts + 1
        await self.db.commit()
        return [job.id for job in jobs]


def _backoff_seconds(attempts: int) -> int:
    return int(min(30 * 2 ** max(attempts - 1, 0), 3600))


async def _embed_version(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, gateway: GatewayClient, version_id: int) -> None:
    """Embed every chunk of a version that has no vector, a batch at a time; raises a GatewayError to stop and retry."""
    while True:
        async with sessionmaker() as db:
            rows = (
                await db.execute(
                    select(ContentChunk).where(ContentChunk.version_id == version_id, ContentChunk.retired.is_(False), ContentChunk.embedding.is_(None)).order_by(ContentChunk.created_at, ContentChunk.id).limit(settings.EMBED_BATCH_SIZE)
                )
            ).scalars().all()
            batch = [(row.id, embedding_text(row)) for row in rows]
        if not batch:
            return
        result = await gateway.embed(organization_id=settings.PLATFORM_ORGANIZATION_ID, user_id=None, texts=[text for _, text in batch])
        if len(result.vectors) != len(batch):
            raise GatewayError(f"ai-gateway returned {len(result.vectors)} vectors for {len(batch)} passages")
        async with sessionmaker() as db:
            for (chunk_id, _), vector in zip(batch, result.vectors, strict=True):
                await db.execute(update(ContentChunk).where(ContentChunk.id == chunk_id).values(embedding=vector, embedding_model=result.model, updated_at=utcnow()))
            await db.commit()


async def index_due(sessionmaker: async_sessionmaker[AsyncSession], settings: Settings, gateway: GatewayClient) -> int:
    """One worker sweep: claim due jobs and embed them. Returns how many jobs it worked on."""
    async with sessionmaker() as db:
        job_ids = await IndexService(db, settings).claim(settings.INDEX_BATCH_SIZE)
    for job_id in job_ids:
        error: str | None = None
        async with sessionmaker() as db:
            job = await db.get(IndexJob, job_id)
            version_id = job.version_id if job else None
        if version_id is None:
            continue
        try:
            await _embed_version(sessionmaker, settings, gateway, version_id)
        except GatewayError as exc:  # unavailable, quota exhausted or AI disabled for the platform org: all retried with backoff
            error = f"{exc.__class__.__name__}: {exc}"[:500]
            logger.warning("indexing version %s will be retried: %s", version_id, error)
        async with sessionmaker() as db:
            job = (await db.execute(select(IndexJob).where(IndexJob.id == job_id).with_for_update().execution_options(populate_existing=True))).scalar_one()
            total, embedded = (
                await db.execute(select(func.count(ContentChunk.id), func.count(ContentChunk.embedding)).where(ContentChunk.version_id == job.version_id, ContentChunk.retired.is_(False)))
            ).one()
            job.chunk_count, job.embedded_count, job.lease_until = int(total), int(embedded), None
            if error is None:
                job.status, job.last_error, job.next_attempt_at = JobStatus.DONE, None, None
            elif job.attempts >= settings.INDEX_MAX_ATTEMPTS:
                job.status, job.last_error = JobStatus.FAILED, error
            else:
                job.status, job.last_error, job.next_attempt_at = JobStatus.PENDING, error, utcnow() + timedelta(seconds=_backoff_seconds(job.attempts))
            await db.commit()
    return len(job_ids)
