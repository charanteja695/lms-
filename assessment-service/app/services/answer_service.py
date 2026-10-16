"""Saving and reading a student's answers while the attempt runs.

The save path is built to touch no database rows: the attempt's state comes from a Redis copy (``AttemptCache``), the
question rules from the cached paper, and the answer goes to the Redis buffer (``AnswerBuffer``), which the worker
flushes in batches. Anything missing from Redis is rebuilt from the database, and if Redis is down the answer is
written straight to the database, so a save never fails just because a cache is unavailable.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, ValidationFailedError
from app.core.time import utcnow
from app.domain.enums import QuestionType
from app.models.attempt import Attempt
from app.services import clock
from app.services.answer_store import AnswerStore
from app.services.attempt_service import AttemptService
from app.storage import s3
from app.validators.answers import normalize_answer

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AnswerItem:
    question_id: int
    response: dict[str, Any] | None
    revision: int = 0
    flagged: bool = False


@dataclass(slots=True)
class SaveResult:
    question_id: int
    status: str  # saved | stale | rejected
    revision: int
    error: dict[str, Any] | None = None


def file_prefix(attempt_public_id: int, question_public_id: int) -> str:
    return f"attempts/{attempt_public_id}/{question_public_id}/"


class AnswerService:
    def __init__(self, db: AsyncSession, settings: Settings, redis: Redis | None = None) -> None:
        self.db = db
        self.settings = settings
        self.attempts = AttemptService(db, settings, redis)
        self.buffer = self.attempts.buffer

    async def save(self, user_id: int, attempt_public_id: int, items: list[AnswerItem]) -> list[SaveResult]:
        meta = await self.attempts.gate(attempt_public_id, user_id)
        paper = {int(q["question_id"]): q for q in await self.attempts.paper(attempt_public_id, uuid.UUID(meta.attempt_id))}
        current = None
        if meta.per_section and meta.deadline_at is not None:
            clocks = list(meta.sections)
            clock.advance(clocks, utcnow(), meta.deadline_at)  # in memory only; the next read persists it
            current = clock.current(clocks)
            if current is None:
                raise ConflictError("Every section is finished.", code="SECTION_CLOSED")

        results: list[SaveResult] = []
        direct: dict[int, dict[str, Any]] = {}
        for item in items:
            question = paper.get(item.question_id)
            if question is None:
                results.append(SaveResult(item.question_id, "rejected", item.revision, {"code": "QUESTION_NOT_IN_ATTEMPT", "message": "This question is not on your paper."}))
                continue
            if current is not None and question["section_position"] != current.position:
                code = "SECTION_CLOSED" if question["section_position"] < current.position else "SECTION_NOT_OPEN"
                results.append(SaveResult(item.question_id, "rejected", item.revision, {"code": code, "message": "This question's section is not the one you are in."}))
                continue
            try:
                normalised = normalize_answer(
                    QuestionType(question["question_type"]),
                    question["body"],
                    item.response,
                    max_bytes=self.settings.MAX_ANSWER_BYTES,
                    file_prefix=file_prefix(attempt_public_id, item.question_id),
                )
            except ValidationFailedError as exc:
                results.append(SaveResult(item.question_id, "rejected", item.revision, exc.details[0] if exc.details else {"code": "INVALID_ANSWER"}))
                continue
            if normalised is not None and question["question_type"] == QuestionType.FILE_SUBMISSION:
                try:
                    normalised = await self._confirm_files(normalised, question["body"])
                except ValidationFailedError as exc:
                    results.append(SaveResult(item.question_id, "rejected", item.revision, exc.details[0]))
                    continue
            record = {"r": normalised, "v": item.revision, "f": item.flagged, "t": utcnow().isoformat()}
            stored = await self.buffer.put(attempt_public_id, item.question_id, record)
            if stored is None:
                direct[item.question_id] = record
                results.append(SaveResult(item.question_id, "saved", item.revision))
            else:
                results.append(SaveResult(item.question_id, "saved" if stored else "stale", item.revision))
        if direct:
            await self._write_direct(meta.attempt_id, direct)
        return results

    async def _confirm_files(self, response: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
        """Each attached file must really be in storage; the size recorded is storage's, not the client's claim."""
        limit = body["max_size_mb"] * 1024 * 1024
        confirmed: list[dict[str, Any]] = []
        for entry in response["files"]:
            try:
                head = await s3.head_object(self.settings, entry["key"])
            except s3.ObjectNotFound:
                raise ValidationFailedError(
                    details=[{"field": "response.files", "code": "FILE_NOT_UPLOADED", "message": f"{entry['filename']} has not been uploaded"}]
                ) from None
            size = int(head.get("ContentLength", 0))
            if not 0 < size <= limit:
                raise ValidationFailedError(details=[{"field": "response.files", "code": "OUT_OF_RANGE", "message": f"Each file must be up to {body['max_size_mb']} MB"}])
            confirmed.append({**entry, "size": size})
        return {"files": confirmed}

    async def _write_direct(self, attempt_id: str, records: dict[int, dict[str, Any]]) -> None:
        store = AnswerStore(self.db)
        for attempt_try in range(2):
            try:
                await store.lock(uuid.UUID(attempt_id))
                await store.upsert(uuid.UUID(attempt_id), records)
                await self.db.commit()
                return
            except IntegrityError:  # a concurrent first write of the same answer: the retry updates it instead
                await self.db.rollback()
                if attempt_try:
                    raise

    async def merged(self, attempt: Attempt) -> dict[int, dict[str, Any]]:
        """The student's answers as they stand: what the database holds, overlaid with newer buffered ones."""
        stored = await AnswerStore(self.db).load(attempt.id)
        merged: dict[int, dict[str, Any]] = {
            qid: {"response": row.response, "flagged": row.flagged, "revision": row.revision} for qid, row in stored.items()
        }
        for qid, record in (await self.buffer.read_all(attempt.public_id)).items():
            if qid not in merged or record["v"] >= merged[qid]["revision"]:
                merged[qid] = {"response": record["r"], "flagged": bool(record.get("f")), "revision": record["v"]}
        return merged
