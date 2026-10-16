"""Persists answers to the database: what the buffer flush and the direct-write fallback both use."""

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models.attempt import Attempt, AttemptAnswer
from app.services.answer_buffer import AnswerBuffer

logger = logging.getLogger(__name__)


class AnswerStore:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def lock(self, attempt_id: uuid.UUID) -> None:
        """Every writer of an attempt's answers takes this row lock first, so writers take turns (no deadlocks)."""
        await self.db.execute(select(Attempt.id).where(Attempt.id == attempt_id).with_for_update())

    async def load(self, attempt_id: uuid.UUID) -> dict[int, AttemptAnswer]:
        rows = (await self.db.execute(select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id))).scalars()
        return {row.question_public_id: row for row in rows}

    async def upsert(self, attempt_id: uuid.UUID, records: dict[int, dict[str, Any]]) -> None:
        """Write answers (keyed by question public id; ``r`` response, ``v`` revision, ``f`` flagged). A record whose
        revision is older than the stored one is skipped. Does not commit."""
        if not records:
            return
        existing = {
            row.question_public_id: row
            for row in (
                await self.db.execute(
                    select(AttemptAnswer).where(
                        AttemptAnswer.attempt_id == attempt_id, AttemptAnswer.question_public_id.in_(records)
                    )
                )
            ).scalars()
        }
        for question_public_id, record in records.items():
            row = existing.get(question_public_id)
            if row is None:
                self.db.add(
                    AttemptAnswer(
                        attempt_id=attempt_id,
                        question_public_id=question_public_id,
                        response=record["r"],
                        revision=record["v"],
                        flagged=bool(record.get("f", False)),
                    )
                )
            elif record["v"] >= row.revision:
                row.response = record["r"]
                row.revision = record["v"]
                row.flagged = bool(record.get("f", False))
                row.updated_at = utcnow()

    async def flush(self, attempt: Attempt, buffer: AnswerBuffer) -> int:
        """Move the attempt's buffered answers into the database and commit. Returns how many were written. On a
        failure the attempt is marked dirty again, so the buffered copy is never lost.

        The attempt's row is locked first, so two writers of the same attempt (the background flush and a submit) take
        turns instead of inserting the same answers at once and deadlocking each other."""
        await self.lock(attempt.id)
        records = await buffer.read_all(attempt.public_id)
        if not records:
            return 0
        try:
            await self.upsert(attempt.id, records)
            await self.db.commit()
        except IntegrityError:  # another worker inserted the same row first: retry as an update
            await self.db.rollback()
            await buffer.requeue(attempt.public_id)
            logger.info("Answer flush raced with another writer; requeued attempt %s", attempt.public_id)
            return 0
        except Exception:
            await self.db.rollback()
            await buffer.requeue(attempt.public_id)
            raise
        return len(records)
