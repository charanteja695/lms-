from datetime import timedelta

from sqlalchemy import func, select, update

from app.core.time import utcnow
from app.models.content import ContentChunk, IndexJob
from app.models.refs import CourseVersionRef, ItemRef
from tests.conftest import COURSE, MEDIA_INTRO, NOTES_RECURSION, VERSION, VIDEO_INTRO, published_payload


async def _chunks(sessionmaker, **where):
    async with sessionmaker() as db:
        rows = (await db.execute(select(ContentChunk).filter_by(**where).order_by(ContentChunk.item_id, ContentChunk.chunk_index))).scalars().all()
        return list(rows)


async def test_publishing_a_course_chunks_its_text_and_queues_embedding(send_event, sessionmaker):
    await send_event("course.published", published_payload())
    chunks = await _chunks(sessionmaker, version_id=VERSION)
    assert [c.item_title for c in chunks] == ["Recursion basics", "Loops", "Fibonacci"]
    assert all(c.embedding is None and c.module_title == "Basics" and c.topic_title == "Functions" for c in chunks)
    async with sessionmaker() as db:
        assert (await db.get(CourseVersionRef, VERSION)).title == "Python Foundations"
        assert (await db.get(ItemRef, NOTES_RECURSION)).topic_title == "Functions"
        assert (await db.execute(select(IndexJob).where(IndexJob.version_id == VERSION))).scalar_one().status == "pending"


async def test_the_worker_embeds_every_chunk_in_batches(send_event, index_now, sessionmaker, gateway):
    await send_event("course.published", published_payload())
    assert await index_now() == 1
    chunks = await _chunks(sessionmaker, version_id=VERSION)
    assert all(c.embedding and c.embedding_model == "voyage-3" for c in chunks)
    assert gateway.embeddings and all(e["organization_id"] == "1755000000000001" and e["service"] == "ai-tutor-service" for e in gateway.embeddings)
    sent = [text for call in gateway.embeddings for text in call["texts"]]
    assert any(text.startswith("Basics > Functions > Recursion basics\n") for text in sent)  # the lesson's place in the course is embedded with it
    assert len(gateway.embeddings) == 1 and len(sent) == 3
    async with sessionmaker() as db:
        job = (await db.execute(select(IndexJob))).scalar_one()
        assert (job.status, job.chunk_count, job.embedded_count) == ("done", 3, 3)
    assert await index_now() == 0  # nothing left to do


async def test_a_redelivered_event_is_applied_once_and_a_republish_replaces_rather_than_duplicates(send_event, sessionmaker):
    await send_event("course.published", published_payload(), event_id="evt-1")
    await send_event("course.published", published_payload(), event_id="evt-1")
    assert len(await _chunks(sessionmaker, version_id=VERSION)) == 3
    await send_event("course.published", published_payload(), event_id="evt-2")
    assert len(await _chunks(sessionmaker, version_id=VERSION)) == 3


async def test_retiring_a_course_retires_its_chunks(send_event, sessionmaker):
    await send_event("course.published", published_payload())
    await send_event("course.retired", {"course_id": str(COURSE), "version_id": str(VERSION)})
    assert all(c.retired for c in await _chunks(sessionmaker, version_id=VERSION))
    async with sessionmaker() as db:
        assert (await db.get(CourseVersionRef, VERSION)).retired is True


async def test_a_transcript_becomes_timestamped_chunks_for_the_video_that_plays_it(send_event, index_now, sessionmaker):
    await send_event("course.published", published_payload(with_video=True))
    segments = [{"start": 0, "end": 30, "text": "Welcome to the course."}, {"start": 30, "end": 70, "text": "Recursion is a function calling itself."}, {"start": 70, "end": 100, "text": "Let us begin."}]
    await send_event("transcript.ready", {"media_asset_id": str(MEDIA_INTRO), "language": "en", "segments": segments})
    transcript = await _chunks(sessionmaker, item_id=VIDEO_INTRO, source="transcript")
    assert transcript and transcript[0].start_seconds == 0 and transcript[0].item_title == "Intro video"
    await index_now()
    assert all(c.embedding for c in await _chunks(sessionmaker, item_id=VIDEO_INTRO, source="transcript"))


async def test_when_the_gateway_is_down_chunks_stay_searchable_and_the_job_is_retried_with_backoff(send_event, index_now, sessionmaker, gateway):
    await send_event("course.published", published_payload())
    gateway.embedding_error = (503, "PROVIDER_UNAVAILABLE")
    assert await index_now() == 1
    async with sessionmaker() as db:
        job = (await db.execute(select(IndexJob))).scalar_one()
        assert job.status == "pending" and job.attempts == 1 and job.last_error and job.next_attempt_at > utcnow()
    assert await index_now() == 0  # not yet due

    gateway.embedding_error = None
    async with sessionmaker() as db:
        await db.execute(update(IndexJob).values(next_attempt_at=utcnow() - timedelta(seconds=1)))
        await db.commit()
    assert await index_now() == 1
    async with sessionmaker() as db:
        assert (await db.execute(select(IndexJob))).scalar_one().status == "done"


async def test_a_job_that_keeps_failing_is_marked_failed(send_event, index_now, sessionmaker, gateway, settings):
    await send_event("course.published", published_payload())
    gateway.embedding_error = (403, "AI_DISABLED")
    for _ in range(settings.INDEX_MAX_ATTEMPTS):
        async with sessionmaker() as db:
            await db.execute(update(IndexJob).values(next_attempt_at=utcnow() - timedelta(seconds=1)))
            await db.commit()
        await index_now()
    async with sessionmaker() as db:
        job = (await db.execute(select(IndexJob))).scalar_one()
        assert job.status == "failed" and "GatewayDisabled" in job.last_error


async def test_an_abandoned_running_job_is_picked_up_after_its_lease_expires(send_event, index_now, sessionmaker):
    await send_event("course.published", published_payload())
    async with sessionmaker() as db:
        await db.execute(update(IndexJob).values(status="running", lease_until=utcnow() - timedelta(seconds=5), attempts=1))
        await db.commit()
    assert await index_now() == 1
    async with sessionmaker() as db:
        assert (await db.execute(select(IndexJob))).scalar_one().status == "done"


async def test_index_status_reports_progress_to_authors(client, who, send_event, index_now):
    await send_event("course.published", published_payload())
    who.author()
    before = (await client.get("/api/v1/index/status", params={"course_id": str(COURSE)})).json()["versions"][0]
    assert (before["chunks"], before["embedded_chunks"], before["job_status"]) == (3, 0, "pending")
    await index_now()
    after = (await client.get("/api/v1/index/status", params={"course_id": str(COURSE)})).json()["versions"][0]
    assert (after["embedded_chunks"], after["job_status"]) == (3, "done")


async def test_reindex_forgets_the_vectors_and_embeds_again(client, who, send_event, index_now, sessionmaker):
    await send_event("course.published", published_payload())
    await index_now()
    who.ai_manager()
    response = await client.post("/api/v1/index/reindex", json={"version_id": str(VERSION)})
    assert response.status_code == 202 and response.json()["versions"][0]["embedded_chunks"] == 0
    await index_now()
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count(ContentChunk.embedding)))).scalar_one() == 3


async def test_only_the_right_people_can_read_or_change_the_index(client, who, send_event):
    await send_event("course.published", published_payload())
    who.student()
    assert (await client.get("/api/v1/index/status", params={"course_id": str(COURSE)})).status_code == 403
    who.author()
    assert (await client.post("/api/v1/index/reindex", json={"version_id": str(VERSION)})).status_code == 403
    who.ai_manager()
    assert (await client.post("/api/v1/index/reindex", json={"version_id": "1755000000099999"})).status_code == 404
    # an AI manager reads the status too: it is where the version ids to reindex come from
    assert (await client.get("/api/v1/index/status", params={"course_id": str(COURSE)})).json()["versions"][0]["version_id"] == str(VERSION)
