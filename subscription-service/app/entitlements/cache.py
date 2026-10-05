"""The Redis entitlement cache (see docs/PRODUCT.md §6.1): "Can student open item / start
test?" is answered by learning-service/assessment-service reading this cache directly
(< 5ms), never by calling this service per check. Built from subscription lifecycle events;
learning-service is not built yet, so nothing reads these keys today — this is the write side,
ready for that consumer.

Key: {prefix}:{organization_id}:{course_id} -> hash {subscription_id, seats_total, seats_used, expires_at}
"""

from typing import Any

from redis.asyncio import Redis

from app.models.subscription import Subscription


def _key(prefix: str, organization_id: int, course_id: int) -> str:
    return f"{prefix}:{organization_id}:{course_id}"


async def sync_entitlement(redis: Redis, *, key_prefix: str, subscription: Subscription) -> None:
    key = _key(key_prefix, subscription.organization_id, subscription.course_id)
    mapping: dict[str, Any] = {
        "subscription_id": str(subscription.public_id),
        "seats_total": subscription.seats_total,
        "seats_used": subscription.seats_used,
        "expires_at": subscription.ends_at.isoformat(),
    }
    await redis.hset(key, mapping=mapping)  # type: ignore[misc]  # redis-py's sync/async overload confuses mypy here
    await redis.expireat(key, int(subscription.ends_at.timestamp()))


async def remove_entitlement(redis: Redis, *, key_prefix: str, organization_id: int, course_id: int) -> None:
    await redis.delete(_key(key_prefix, organization_id, course_id))
