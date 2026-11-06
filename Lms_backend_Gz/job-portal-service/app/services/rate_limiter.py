import logging
import time

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.exceptions import RateLimitedError

logger = logging.getLogger(__name__)


class RateLimiter:
    """Fixed-window counter in Redis. Fails open if Redis is unavailable: quota enforcement (Postgres,
    under a row lock) is the real spending control, so this is only a burst guard."""

    def __init__(self, redis: Redis, *, enabled: bool = True) -> None:
        self.redis = redis
        self.enabled = enabled

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> None:
        if not self.enabled:
            return
        now = int(time.time())
        window = now // window_seconds
        redis_key = f"ratelimit:{key}:{window}"
        try:
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.incr(redis_key)
                pipe.expire(redis_key, window_seconds + 1)
                count, _ = await pipe.execute()
        except RedisError:
            logger.warning("Rate limiter unavailable; allowing request", extra={"extra_fields": {"key": key}})
            return
        if int(count) > limit:
            raise RateLimitedError(retry_after=window_seconds - (now % window_seconds))
