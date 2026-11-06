"""Question usage statistics (docs/PRODUCT.md §5.1: "difficulty index, discrimination computed after attempts").

  difficulty index  the average share of the marks students earned on the question (0-1; high = easy)
  discrimination    that share among the top 27% of scorers on the whole test minus the bottom 27%
                    (-1..1; high = the question separates strong from weak, near 0 or negative = a poor question)

Computed from the most recent graded, non-invalidated attempts, only when enough attempts exist for the numbers to
mean something. A finalised attempt marks its test dirty in Redis and the worker refreshes that test's questions.
"""

import logging
import uuid
from dataclasses import dataclass

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.time import utcnow
from app.domain.enums import AttemptResult, AttemptStatus
from app.models.attempt import Attempt, AttemptAnswer, AttemptQuestion
from app.models.question import Question, QuestionStats
from app.services.result_service import STATS_DIRTY_SET

logger = logging.getLogger(__name__)

_TAIL = 0.27


@dataclass(frozen=True, slots=True)
class Computed:
    sample_size: int
    difficulty_index: float | None
    discrimination: float | None


def compute_stats(rows: list[tuple[float, float]], *, min_sample: int) -> Computed:
    """``rows`` are (share of the question's marks earned, the attempt's overall percent), one per attempt."""
    n = len(rows)
    if n == 0:
        return Computed(0, None, None)
    difficulty = round(sum(share for share, _ in rows) / n, 4)
    if n < min_sample:
        return Computed(n, difficulty, None)
    ranked = sorted(rows, key=lambda row: row[1])
    tail = max(1, round(n * _TAIL))
    bottom = sum(share for share, _ in ranked[:tail]) / tail
    top = sum(share for share, _ in ranked[-tail:]) / tail
    return Computed(n, difficulty, round(top - bottom, 4))


class StatsService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def recompute_question(self, question: Question) -> QuestionStats | None:
        rows = (
            await self.db.execute(
                select(AttemptAnswer.marks_awarded, AttemptAnswer.max_marks, Attempt.percent)
                .join(Attempt, Attempt.id == AttemptAnswer.attempt_id)
                .where(
                    AttemptAnswer.question_public_id == question.public_id,
                    AttemptAnswer.max_marks > 0,
                    AttemptAnswer.marks_awarded.is_not(None),
                    Attempt.status == AttemptStatus.GRADED,
                    Attempt.result != AttemptResult.INVALIDATED,
                    Attempt.percent.is_not(None),
                )
                .order_by(Attempt.graded_at.desc())
                .limit(self.settings.STATS_SAMPLE_LIMIT)
            )
        ).all()
        computed = compute_stats(
            [(max(0.0, min(1.0, float(marks) / float(maximum))), float(percent)) for marks, maximum, percent in rows],
            min_sample=self.settings.STATS_MIN_SAMPLE,
        )
        stats = await self.db.get(QuestionStats, question.id)
        if stats is None:
            stats = QuestionStats(question_id=question.id, computed_at=utcnow())
            self.db.add(stats)
        stats.sample_size, stats.difficulty_index, stats.discrimination = computed.sample_size, computed.difficulty_index, computed.discrimination
        stats.computed_at = utcnow()
        await self.db.commit()
        return stats

    async def recompute_test(self, test_public_id: int) -> int:
        ids = (
            await self.db.execute(
                select(AttemptQuestion.question_id)
                .join(Attempt, Attempt.id == AttemptQuestion.attempt_id)
                .where(Attempt.test_public_id == test_public_id, Attempt.status == AttemptStatus.GRADED)
                .distinct()
                .limit(1_000)
            )
        ).scalars().all()
        count = 0
        for question_id in ids:
            question = await self.db.get(Question, uuid.UUID(str(question_id)))
            if question is not None:
                await self.recompute_question(question)
                count += 1
        return count


async def process_dirty(
    sessionmaker: async_sessionmaker[AsyncSession], redis: Redis, settings: Settings, limit: int = 5
) -> int:
    """Refresh statistics for tests that finished attempts since the last sweep."""
    done = 0
    for _ in range(limit):
        try:
            popped = await redis.spop(STATS_DIRTY_SET)  # type: ignore[misc]
        except RedisError:
            return done
        if popped is None:
            break
        try:
            async with sessionmaker() as db:
                await StatsService(db, settings).recompute_test(int(popped))
            done += 1
        except Exception:
            logger.exception("Statistics refresh failed for test %s", popped)
            try:
                await redis.sadd(STATS_DIRTY_SET, popped)  # type: ignore[misc]
            except RedisError:
                pass
            break
    return done
