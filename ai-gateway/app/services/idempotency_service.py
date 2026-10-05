"""Idempotent replay for completions and embeddings, cached in Redis with a TTL rather than kept in Postgres —
see app/models/__init__.py's note on why. A retried ``Idempotency-Key`` (a double click, a network retry on the
calling service's side) returns the exact same result instead of spending quota and calling a provider twice.
"""

import hashlib
import json
from typing import Any

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.exceptions import ConflictError


def request_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class IdempotencyCache:
    def __init__(self, redis: Redis, settings: Settings) -> None:
        self.redis = redis
        self.ttl_seconds = settings.IDEMPOTENCY_RETENTION_HOURS * 3600

    def _key(self, organization_id: int, scope: str, key: str) -> str:
        return f"ai:idem:{organization_id}:{scope}:{key}"

    async def find(self, organization_id: int, scope: str, key: str, payload_hash: str) -> dict[str, Any] | None:
        raw = await self.redis.get(self._key(organization_id, scope, key))
        if raw is None:
            return None
        cached = json.loads(raw)
        if cached["request_hash"] != payload_hash:
            raise ConflictError("This Idempotency-Key was already used for a different request.", code="IDEMPOTENCY_KEY_REUSED")
        result: dict[str, Any] = cached["response"]
        return result

    async def remember(self, organization_id: int, scope: str, key: str, payload_hash: str, response: dict[str, Any]) -> None:
        await self.redis.set(
            self._key(organization_id, scope, key),
            json.dumps({"request_hash": payload_hash, "response": response}, default=str),
            ex=self.ttl_seconds,
        )
