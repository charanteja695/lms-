"""Reads the Redis entitlement cache subscription-service writes on every subscription
lifecycle change (see subscription-service/app/entitlements/cache.py) — this is what lets
"is this institution entitled to this course?" be answered in under 5ms (docs/PRODUCT.md §6.1)
without calling subscription-service per check. Both services must point at the same Redis
instance/db for this to work (they share the ``lms:entitlement:*`` keyspace by convention, the
same way every service shares ``lms:access:*`` and the ``lms:events`` stream).
"""

from dataclasses import dataclass

from redis.asyncio import Redis

DEFAULT_KEY_PREFIX = "lms:entitlement"


@dataclass(frozen=True, slots=True)
class Entitlement:
    subscription_id: int


async def get_entitlement(
    redis: Redis, *, key_prefix: str = DEFAULT_KEY_PREFIX, organization_id: int, course_id: int
) -> Entitlement | None:
    key = f"{key_prefix}:{organization_id}:{course_id}"
    subscription_id = await redis.hget(key, "subscription_id")  # type: ignore[misc]  # redis-py's sync/async overload confuses mypy here
    if subscription_id is None:
        return None
    return Entitlement(subscription_id=int(subscription_id))
