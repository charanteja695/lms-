"""Redis copies of what the answer-save hot path needs, so a save touches no database rows.

* ``meta``  the attempt's owner, status, deadline and section clocks (rewritten whenever any of them changes);
* ``paper`` the student view of the paper (no answer keys): also what validates each answer.

Both are only caches of the database: a miss (Redis restarted, key expired, Redis down) is rebuilt from it, and
nothing here is ever the only copy of anything.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.services.clock import SectionClock

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AttemptMeta:
    attempt_id: str  # the row's uuid
    public_id: int
    user_id: int
    status: str
    deadline_at: datetime | None
    per_section: bool = False
    sections: list[SectionClock] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(
            {
                "attempt_id": self.attempt_id,
                "public_id": self.public_id,
                "user_id": self.user_id,
                "status": self.status,
                "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
                "per_section": self.per_section,
                "sections": [section.to_dict() for section in self.sections],
            }
        )

    @classmethod
    def from_json(cls, raw: str) -> "AttemptMeta":
        data: dict[str, Any] = json.loads(raw)
        return cls(
            attempt_id=data["attempt_id"],
            public_id=data["public_id"],
            user_id=data["user_id"],
            status=data["status"],
            deadline_at=datetime.fromisoformat(data["deadline_at"]) if data["deadline_at"] else None,
            per_section=data["per_section"],
            sections=[SectionClock.from_dict(section) for section in data["sections"]],
        )


class AttemptCache:
    def __init__(self, redis: Redis | None, settings: Settings) -> None:
        self.redis = redis
        self.ttl = settings.ANSWER_BUFFER_TTL_HOURS * 3600

    @staticmethod
    def _meta_key(public_id: int) -> str:
        return f"assessment:attempt:{public_id}:meta"

    @staticmethod
    def _paper_key(public_id: int) -> str:
        return f"assessment:attempt:{public_id}:paper"

    async def _get(self, key: str) -> str | None:
        if self.redis is None:
            return None
        try:
            value = await self.redis.get(key)
        except RedisError:
            logger.warning("Attempt cache unavailable; reading from the database")
            return None
        return None if value is None else str(value)

    async def _set(self, key: str, value: str) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.set(key, value, ex=self.ttl)
        except RedisError:
            logger.warning("Attempt cache unavailable; skipping write")

    async def get_meta(self, public_id: int) -> AttemptMeta | None:
        raw = await self._get(self._meta_key(public_id))
        return AttemptMeta.from_json(raw) if raw else None

    async def put_meta(self, meta: AttemptMeta) -> None:
        await self._set(self._meta_key(meta.public_id), meta.to_json())

    async def drop_meta(self, public_id: int) -> None:
        if self.redis is None:
            return
        try:
            await self.redis.delete(self._meta_key(public_id))
        except RedisError:
            logger.warning("Attempt cache unavailable; could not drop meta")

    async def get_paper(self, public_id: int) -> list[dict[str, Any]] | None:
        raw = await self._get(self._paper_key(public_id))
        return json.loads(raw) if raw else None

    async def put_paper(self, public_id: int, questions: list[dict[str, Any]]) -> None:
        await self._set(self._paper_key(public_id), json.dumps(questions, separators=(",", ":"), ensure_ascii=False))
