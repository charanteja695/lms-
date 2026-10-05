"""Which questions may a pool slot draw from. Used when a test is published (is there enough to draw?) and every
time a paper is generated.

Criteria semantics: a question matches when it is active, published, owned by the test's owner, of an allowed type,
within the difficulty range, and — for each of ``skills`` / ``topics`` / ``tags`` / ``bloom`` given — has at least one
of the listed values (any-of within a kind, all kinds must match).

The eligible list is cached in Redis per slot for a few minutes: at exam time thousands of students generate a paper
from the same few pools, and a published test's pools rarely change. A newly approved question therefore joins a pool
after at most ``POOL_CACHE_SECONDS``.
"""

import json
import logging
import uuid
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.enums import QuestionStatus, TagType
from app.models.question import Question, QuestionVersion, QuestionVersionTag

logger = logging.getLogger(__name__)

Candidate = tuple[uuid.UUID, uuid.UUID]  # (question id, published version id)


def criteria_filters(criteria: dict[str, Any]) -> list[Any]:
    filters: list[Any] = []
    if criteria.get("types"):
        filters.append(Question.question_type.in_(criteria["types"]))
    if criteria.get("difficulty_min"):
        filters.append(QuestionVersion.difficulty >= criteria["difficulty_min"])
    if criteria.get("difficulty_max"):
        filters.append(QuestionVersion.difficulty <= criteria["difficulty_max"])
    if criteria.get("bloom"):
        filters.append(QuestionVersion.bloom.in_(criteria["bloom"]))
    for tag_type, key in ((TagType.SKILL, "skills"), (TagType.TOPIC, "topics"), (TagType.TAG, "tags")):
        if criteria.get(key):
            filters.append(
                exists().where(
                    QuestionVersionTag.version_id == QuestionVersion.id,
                    QuestionVersionTag.tag_type == tag_type,
                    QuestionVersionTag.value.in_([value.strip().lower() for value in criteria[key]]),
                )
            )
    return filters


class PoolIndex:
    def __init__(self, db: AsyncSession, redis: Redis | None, settings: Settings) -> None:
        self.db = db
        self.redis = redis
        self.settings = settings

    async def eligible(
        self, owner_organization_id: int | None, criteria: dict[str, Any], *, cache_key: str | None = None
    ) -> list[Candidate]:
        cached = await self._cached(cache_key)
        if cached is not None:
            return cached
        stmt = (
            select(Question.id, QuestionVersion.id)
            .join(
                QuestionVersion,
                and_(QuestionVersion.question_id == Question.id, QuestionVersion.version_no == Question.current_version_no),
            )
            .where(
                Question.status == QuestionStatus.ACTIVE,
                Question.organization_id.is_(None) if owner_organization_id is None else Question.organization_id == owner_organization_id,
                *criteria_filters(criteria),
            )
            .order_by(Question.public_id)
            .limit(self.settings.POOL_MAX_CANDIDATES)
        )
        candidates = [(row[0], row[1]) for row in (await self.db.execute(stmt)).all()]
        await self._store(cache_key, candidates)
        return candidates

    async def _cached(self, cache_key: str | None) -> list[Candidate] | None:
        if not cache_key or self.redis is None or not self.settings.POOL_CACHE_SECONDS:
            return None
        try:
            raw = await self.redis.get(f"assessment:pool:{cache_key}")
        except RedisError:
            return None
        if raw is None:
            return None
        return [(uuid.UUID(question), uuid.UUID(version)) for question, version in json.loads(raw)]

    async def _store(self, cache_key: str | None, candidates: list[Candidate]) -> None:
        if not cache_key or self.redis is None or not self.settings.POOL_CACHE_SECONDS:
            return
        try:
            await self.redis.set(
                f"assessment:pool:{cache_key}",
                json.dumps([[str(question), str(version)] for question, version in candidates]),
                ex=self.settings.POOL_CACHE_SECONDS,
            )
        except RedisError:
            logger.warning("Pool cache unavailable; drawing without it")
