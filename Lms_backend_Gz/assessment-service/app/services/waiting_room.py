"""Staggered starts (docs/PRODUCT.md §5.1 "Exam starts are staggered with a waiting room").

When a scheduled exam opens, everyone clicks Start in the same second. Admitting them all at once would stampede
the paper, timer and answer paths, so at most ``WAITING_ROOM_ADMIT_PER_SECOND`` starts per test are admitted each
second and the rest are told to retry after a small random delay (which also spreads the retries). The waiting
student's paper is already prepared, so admission is a cheap state change once it is their turn.
"""

import logging
import random
import time

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


class WaitingRoomError(AppError):
    status_code = 429
    code = "WAITING_ROOM"
    message = "The exam room is busy. Please wait a moment; you will be let in shortly."

    def __init__(self, retry_after: int) -> None:
        super().__init__(headers={"Retry-After": str(retry_after)})
        self.retry_after = retry_after


async def admit(redis: Redis | None, settings: Settings, test_public_id: int) -> None:
    """Return if this start may go ahead now, else raise WaitingRoomError. Fails open if Redis is unavailable: a
    thundering herd is better than locking every student out of their exam."""
    if redis is None:
        return
    second = int(time.time())
    key = f"assessment:admit:{test_public_id}:{second}"
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, 5)
            count, _ = await pipe.execute()
    except RedisError:
        logger.warning("Waiting room unavailable; admitting")
        return
    if int(count) > settings.WAITING_ROOM_ADMIT_PER_SECOND:
        raise WaitingRoomError(retry_after=1 + random.randint(0, 2))  # noqa: S311  (spreads retries, not security)
