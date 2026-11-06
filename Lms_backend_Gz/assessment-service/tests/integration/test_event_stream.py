"""The service's events on the real wire: its outbox relayed to the Redis stream in the shape other services read, and
inbound events consumed through the shared ``StreamConsumer``. Sequential on purpose (a blocking XREADGROUP and a
writer on separate fakeredis clients hang, see the notes in the other services)."""

import json

from lms_common.events import StreamConsumer
from sqlalchemy import select

from app.events.consumers.router import dispatch
from app.events.publisher import RedisStreamPublisher, relay_outbox
from app.models.outbox_event import OutboxEvent
from tests.conftest import COURSE, ENROLLMENT, MODULE, STUDENT, VERSION, fixed, mcq


async def test_the_outbox_is_relayed_to_lms_events_with_the_shared_envelope(client, who, make_question, make_test, sessionmaker, redis, settings):
    q1 = await make_question(mcq())
    test_id = await make_test([fixed(q1, 2)], kind="module", target_id=str(MODULE))

    published = await relay_outbox(sessionmaker, RedisStreamPublisher(redis, settings), batch_size=50)
    assert published == 1
    (_, fields), = await redis.xrange(settings.EVENTS_STREAM)
    assert fields["event_type"] == "test.published" and fields["aggregate_type"] == "test"
    assert json.loads(fields["payload"])["test_id"] == test_id
    async with sessionmaker() as db:
        assert (await db.execute(select(OutboxEvent.published_at))).scalar_one() is not None
    assert await relay_outbox(sessionmaker, RedisStreamPublisher(redis, settings), batch_size=50) == 0  # nothing is sent twice


async def test_inbound_events_flow_through_the_consumer_group_into_the_read_models(client, who, make_question, make_test, sessionmaker, redis, settings):
    q1 = await make_question(mcq())
    test_id = await make_test([fixed(q1)], kind="module", target_id=str(MODULE))
    consumer = StreamConsumer(redis, stream=settings.EVENTS_STREAM, group=settings.EVENTS_CONSUMER_GROUP, name="worker-1", block_ms=100)
    await consumer.ensure_group()

    for event_type, payload in (
        ("course.published", {"course_id": str(COURSE), "version_id": str(VERSION), "modules": [{"module_id": str(MODULE), "topics": []}]}),
        ("enrollment.created", {"enrollment_id": str(ENROLLMENT), "student_user_id": str(STUDENT), "organization_id": "1755000000007003", "version_id": str(VERSION)}),
    ):
        await redis.xadd(
            settings.EVENTS_STREAM,
            {"event_id": f"evt-{event_type}", "event_type": event_type, "aggregate_type": "x", "occurred_time": "2026-09-21T10:00:00Z", "payload": json.dumps(payload)},
        )
    handled = 0
    async for event in consumer.read():
        async with sessionmaker() as db:
            await dispatch(db, event, settings, redis)
            await db.commit()
        await consumer.ack(event)
        handled += 1
    assert handled == 2

    who.student()
    assert (await client.post(f"/api/v1/tests/{test_id}/attempts", json={})).status_code == 201  # the student can now take the test
    pending = await redis.xpending(settings.EVENTS_STREAM, settings.EVENTS_CONSUMER_GROUP)
    assert pending["pending"] == 0
