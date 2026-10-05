"""Answer writes go to Redis first and are flushed to PostgreSQL in batches (docs/PRODUCT.md §5.1 "Scale").

A save is one Redis hash write plus a mark in a "dirty" set; the worker later moves the dirty attempts' answers into
the database. That keeps the database out of the per-keystroke path (200k students saving every few seconds), while
Redis persistence (AOF) plus the short flush interval bound what a Redis failure could lose.

Each answer carries the client's ``revision`` (a counter it bumps on every change), and an older revision never
overwrites a newer one, so requests that arrive out of order cannot resurrect a stale answer.
"""

import json
import logging
import time
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError, WatchError

from app.core.config import Settings

logger = logging.getLogger(__name__)

DIRTY_SET = "assessment:answers:dirty"
_WATCH_RETRIES = 5


class AnswerBuffer:
    def __init__(self, redis: Redis | None, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.redis is not None and self.settings.ANSWER_BUFFER == "redis"

    @staticmethod
    def _key(attempt_public_id: int) -> str:
        return f"assessment:answers:{attempt_public_id}"

    async def put(self, attempt_public_id: int, question_public_id: int, record: dict[str, Any]) -> bool | None:
        """Buffer one answer. True: stored. False: a newer revision is already stored. None: the buffer could not be
        used (the caller must write to the database instead)."""
        if not self.enabled or self.redis is None:
            return None
        key, field = self._key(attempt_public_id), str(question_public_id)
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                for _ in range(_WATCH_RETRIES):
                    try:
                        await pipe.watch(key)
                        current = await pipe.hget(key, field)  # type: ignore[misc]
                        if current is not None and json.loads(current)["v"] > record["v"]:
                            await pipe.unwatch()  # type: ignore[no-untyped-call]
                            return False
                        pipe.multi()  # type: ignore[no-untyped-call]
                        pipe.hset(key, field, json.dumps(record, separators=(",", ":"), ensure_ascii=False))
                        pipe.zadd(DIRTY_SET, {str(attempt_public_id): time.time()})
                        pipe.expire(key, self.settings.ANSWER_BUFFER_TTL_HOURS * 3600)
                        await pipe.execute()
                        return True
                    except WatchError:
                        continue
        except RedisError:
            logger.warning("Answer buffer unavailable; writing to the database")
        return None

    async def read_all(self, attempt_public_id: int) -> dict[int, dict[str, Any]]:
        if not self.enabled or self.redis is None:
            return {}
        try:
            raw = await self.redis.hgetall(self._key(attempt_public_id))  # type: ignore[misc]
        except RedisError:
            logger.warning("Answer buffer unavailable; reading only what the database holds")
            return {}
        return {int(field): json.loads(value) for field, value in raw.items()}

    async def take_dirty(self, limit: int) -> list[int]:
        """Claim up to ``limit`` attempts with unflushed answers. ZREM is atomic, so of several workers exactly one
        wins each attempt; a save that arrives while it is being flushed marks the attempt dirty again."""
        if not self.enabled or self.redis is None:
            return []
        try:
            candidates = await self.redis.zrange(DIRTY_SET, 0, limit - 1)
            claimed = [int(member) for member in candidates if await self.redis.zrem(DIRTY_SET, member)]
        except RedisError:
            logger.warning("Answer buffer unavailable; nothing to flush")
            return []
        return claimed

    async def requeue(self, attempt_public_id: int) -> None:
        """A flush failed: put the attempt back so the next sweep retries it."""
        if self.redis is None:
            return
        try:
            await self.redis.zadd(DIRTY_SET, {str(attempt_public_id): time.time()})
        except RedisError:
            logger.error("Could not requeue attempt %s for flushing", attempt_public_id)

    async def clear(self, attempt_public_id: int) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.delete(self._key(attempt_public_id))
            await self.redis.zrem(DIRTY_SET, str(attempt_public_id))
        except RedisError:
            logger.warning("Answer buffer unavailable; could not clear attempt %s", attempt_public_id)

    async def dirty_count(self) -> int:
        if not self.enabled or self.redis is None:
            return 0
        try:
            return int(await self.redis.zcard(DIRTY_SET))
        except RedisError:
            return 0
