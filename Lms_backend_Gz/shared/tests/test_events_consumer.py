import json

from fakeredis import FakeAsyncRedis
from lms_common.events import StreamConsumer

STREAM, GROUP = "lms:events", "catalog"


async def _publish(redis: FakeAsyncRedis, event_type: str, payload: dict[str, object], *, event_id: str | None = None) -> None:
    await redis.xadd(
        STREAM,
        {
            "event_id": event_id or f"evt-{event_type}",
            "event_type": event_type,
            "aggregate_type": "user",
            "occurred_time": "2026-09-18T10:00:00Z",
            "payload": json.dumps(payload),
        },
    )


def _consumer(redis: FakeAsyncRedis, name: str = "worker-1", **options: object) -> StreamConsumer:
    """A consumer that reclaims immediately, so redelivery can be tested without waiting."""
    settings: dict[str, object] = {"block_ms": 50, "redeliver_after_ms": 0, "reclaim_every_seconds": 0}
    return StreamConsumer(redis, stream=STREAM, group=GROUP, name=name, **{**settings, **options})  # type: ignore[arg-type]


async def _pending(redis: FakeAsyncRedis) -> int:
    return int((await redis.xpending(STREAM, GROUP))["pending"])


async def test_consumer_reads_and_acks_new_events() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    consumer = _consumer(redis)
    await consumer.ensure_group()

    await _publish(redis, "user.created", {"user_id": "1"})
    events = [event async for event in consumer.read()]
    assert len(events) == 1
    assert events[0].event_type == "user.created" and events[0].payload == {"user_id": "1"}

    await consumer.ack(events[0])
    assert await _pending(redis) == 0


async def test_ensure_group_is_idempotent() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    consumer = _consumer(redis)
    await consumer.ensure_group()
    await consumer.ensure_group()  # must not raise BUSYGROUP


async def test_unacked_event_stays_pending() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    consumer = _consumer(redis, redeliver_after_ms=60_000)
    await consumer.ensure_group()
    await _publish(redis, "user.updated", {"user_id": "1"})

    assert len([event async for event in consumer.read()]) == 1
    assert await _pending(redis) == 1  # no ack: still held for redelivery


async def test_event_whose_handler_failed_is_redelivered() -> None:
    """The bug this fixes: an event that was read but never acked used to be lost to the consumer forever."""
    redis = FakeAsyncRedis(decode_responses=True)
    consumer = _consumer(redis)
    await consumer.ensure_group()
    await _publish(redis, "user.updated", {"user_id": "1"})

    first = [event async for event in consumer.read()]
    assert len(first) == 1  # the handler "raised": no ack

    second = [event async for event in consumer.read()]
    assert [event.event_id for event in second] == [first[0].event_id]
    await consumer.ack(second[0])
    assert await _pending(redis) == 0
    assert [event async for event in consumer.read()] == []  # acked events are not delivered again


async def test_another_instance_picks_up_what_a_crashed_one_left_behind() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    crashed, healthy = _consumer(redis, "worker-1"), _consumer(redis, "worker-2")
    await crashed.ensure_group()
    await _publish(redis, "user.updated", {"user_id": "1"})
    assert len([event async for event in crashed.read()]) == 1  # then the process dies

    rescued = [event async for event in healthy.read()]
    assert len(rescued) == 1
    await healthy.ack(rescued[0])
    assert await _pending(redis) == 0


async def test_event_is_not_redelivered_before_it_has_been_idle_long_enough() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    consumer = _consumer(redis, redeliver_after_ms=60_000)  # a slow handler must not be handed out twice
    await consumer.ensure_group()
    await _publish(redis, "user.updated", {"user_id": "1"})

    assert len([event async for event in consumer.read()]) == 1
    assert [event async for event in consumer.read()] == []


async def test_reclaiming_is_rate_limited() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    consumer = _consumer(redis, reclaim_every_seconds=3600)
    await consumer.ensure_group()
    await _publish(redis, "user.updated", {"user_id": "1"})
    assert len([event async for event in consumer.read()]) == 1

    assert [event async for event in consumer.read()] == []  # the reclaim scan just ran; not again for an hour


async def test_a_poison_event_is_dead_lettered_after_max_deliveries() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    consumer = _consumer(redis, max_deliveries=3)
    await consumer.ensure_group()
    await _publish(redis, "user.updated", {"user_id": "1"}, event_id="evt-poison")

    seen = 0
    for _ in range(10):  # the handler always raises, so nothing is ever acked
        seen += len([event async for event in consumer.read()])
    assert seen == 3

    assert await _pending(redis) == 0  # acked off the group's list so it stops coming back
    dead = await redis.xrange("lms:events:dead")
    assert len(dead) == 1
    fields = dead[0][1]
    assert fields["event_id"] == "evt-poison" and fields["deliveries"] == "4" and fields["group"] == GROUP
    assert fields["reason"] == "too many failed deliveries"


async def test_a_malformed_message_is_dead_lettered_and_does_not_block_the_next_one() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    consumer = _consumer(redis)
    await consumer.ensure_group()
    await redis.xadd(STREAM, {"event_id": "evt-broken", "payload": "{not json"})  # missing fields
    await _publish(redis, "user.created", {"user_id": "2"}, event_id="evt-good")

    events = [event async for event in consumer.read()]
    assert [event.event_id for event in events] == ["evt-good"]
    dead = await redis.xrange("lms:events:dead")
    assert len(dead) == 1 and dead[0][1]["reason"].startswith("malformed")
    await consumer.ack(events[0])
    assert await _pending(redis) == 0


async def test_a_pending_entry_trimmed_from_the_stream_is_dropped() -> None:
    redis = FakeAsyncRedis(decode_responses=True)
    consumer = _consumer(redis)
    await consumer.ensure_group()
    await _publish(redis, "user.updated", {"user_id": "1"})
    assert len([event async for event in consumer.read()]) == 1
    await redis.xtrim(STREAM, maxlen=0)  # retention removed it while it was still unacked

    assert [event async for event in consumer.read()] == []
    assert await _pending(redis) == 0
