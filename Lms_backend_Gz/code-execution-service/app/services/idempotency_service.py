import hashlib
import json
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.core.time import utcnow
from app.domain.enums import IdempotentScope
from app.models.idempotency_key import IdempotencyKey


def request_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class IdempotencyService:
    """A retried create must return the run or submission it already made, not judge the same code twice."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def find(self, user_id: int, scope: IdempotentScope, key: str, payload_hash: str) -> int | None:
        """The public id already created for this key, or None. Reusing a key for a different request is a
        client bug and is refused rather than silently returning the wrong resource."""
        row = (
            await self.db.execute(
                select(IdempotencyKey).where(
                    IdempotencyKey.user_id == user_id, IdempotencyKey.scope == scope, IdempotencyKey.key == key
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        if row.request_hash != payload_hash:
            raise ConflictError(
                "This Idempotency-Key was already used for a different request.", code="IDEMPOTENCY_KEY_REUSED"
            )
        return row.resource_public_id

    def remember(self, user_id: int, scope: IdempotentScope, key: str, payload_hash: str, resource_public_id: int) -> None:
        self.db.add(
            IdempotencyKey(
                user_id=user_id, scope=scope, key=key, request_hash=payload_hash, resource_public_id=resource_public_id
            )
        )

    async def prune(self, *, retention_hours: int) -> int:
        result = await self.db.execute(
            delete(IdempotencyKey).where(IdempotencyKey.created_at < utcnow() - timedelta(hours=retention_hours))
        )
        await self.db.commit()
        return int(getattr(result, "rowcount", 0) or 0)
