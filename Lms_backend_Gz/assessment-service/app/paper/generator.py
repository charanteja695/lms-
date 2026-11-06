"""Builds one student's question paper (docs/PRODUCT.md §5.1: "per-student question set from the pool").

The paper is a pure function of the published test and a seed, so it can be audited and regenerated: fixed slots give
their question; pool slots draw ``count`` questions, without repeating any question already on the paper, using a
random generator seeded from the attempt's seed and the slot. Questions may then be shuffled within a section, and
option lists are shuffled (always for matching and ordering, where the listed order would give the answer away).
"""

import random
import uuid
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AppError
from app.domain.enums import QuestionStatus, QuestionType, SlotType
from app.models.question import Question, QuestionVersion
from app.models.test import Test, TestSection
from app.paper.pool import PoolIndex


class PaperGenerationError(AppError):
    status_code = 503
    code = "PAPER_GENERATION_FAILED"
    message = "This test's paper could not be prepared right now. Please try again shortly."


@dataclass(slots=True)
class PlannedQuestion:
    section: TestSection
    question: Question
    version: QuestionVersion
    marks: float
    option_order: list[str] | None


def _option_ids(qtype: str, body: dict[str, Any]) -> list[str] | None:
    if qtype in (QuestionType.MCQ_SINGLE, QuestionType.MCQ_MULTI):
        return [option["id"] for option in body["options"]]
    if qtype == QuestionType.MATCH:
        return [item["id"] for item in body["right"]]
    if qtype == QuestionType.ORDERING:
        return [item["id"] for item in body["items"]]
    return None


def _shuffled_options(
    qtype: str, body: dict[str, Any], key: dict[str, Any], seed: int, question_id: uuid.UUID, shuffle_options: bool
) -> list[str] | None:
    ids = _option_ids(qtype, body)
    if ids is None:
        return None
    always = qtype in (QuestionType.MATCH, QuestionType.ORDERING)
    if not (shuffle_options or always):
        return ids
    rng = random.Random(f"{seed}:options:{question_id}")  # noqa: S311  (fairness shuffle, not security)
    order = list(ids)
    rng.shuffle(order)
    if qtype == QuestionType.ORDERING and len(order) > 1 and order == key.get("order"):
        order.reverse()  # never hand out the answer as the starting arrangement
    return order


class PaperGenerator:
    def __init__(self, db: AsyncSession, redis: Redis | None, settings: Settings) -> None:
        self.db = db
        self.settings = settings
        self.pools = PoolIndex(db, redis, settings)

    async def generate(self, test: Test, seed: int) -> list[PlannedQuestion]:
        """The paper, in order. ``test`` must have its sections and slots loaded."""
        fixed_ids = {slot.question_id for section in test.sections for slot in section.slots if slot.question_id}
        fixed_versions = await self._current_versions(fixed_ids)
        chosen: set[uuid.UUID] = set(fixed_ids)
        picks: list[tuple[TestSection, uuid.UUID, uuid.UUID, float]] = []  # (section, question id, version id, marks)
        for section in test.sections:
            section_picks: list[tuple[TestSection, uuid.UUID, uuid.UUID, float]] = []
            for slot in section.slots:
                if slot.slot_type == SlotType.FIXED:
                    version_id = fixed_versions.get(slot.question_id) if slot.question_id else None
                    if slot.question_id is None or version_id is None:
                        raise PaperGenerationError("A question in this test is no longer available.", code="QUESTION_UNAVAILABLE")
                    section_picks.append((section, slot.question_id, version_id, slot.marks))
                    continue
                candidates = [c for c in await self.pools.eligible(test.organization_id, slot.criteria or {}, cache_key=str(slot.id)) if c[0] not in chosen]
                if len(candidates) < slot.count:
                    raise PaperGenerationError(
                        "This test does not have enough questions available right now.", code="POOL_TOO_SMALL"
                    )
                rng = random.Random(f"{seed}:slot:{slot.id}")  # noqa: S311
                for question_id, version_id in rng.sample(candidates, slot.count):
                    chosen.add(question_id)
                    section_picks.append((section, question_id, version_id, slot.marks))
            if test.shuffle_questions:
                random.Random(f"{seed}:order:{section.id}").shuffle(section_picks)  # noqa: S311
            picks.extend(section_picks)

        versions = await self._versions_by_id({version_id for _, _, version_id, _ in picks})
        planned: list[PlannedQuestion] = []
        for section, question_id, version_id, marks in picks:
            question, version = versions[version_id]
            planned.append(
                PlannedQuestion(
                    section=section,
                    question=question,
                    version=version,
                    marks=marks,
                    option_order=_shuffled_options(
                        question.question_type, version.body, version.answer_key, seed, question_id, test.shuffle_options
                    ),
                )
            )
        return planned

    async def _current_versions(self, question_ids: set[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
        if not question_ids:
            return {}
        rows = await self.db.execute(
            select(Question.id, QuestionVersion.id)
            .join(QuestionVersion, and_(QuestionVersion.question_id == Question.id, QuestionVersion.version_no == Question.current_version_no))
            .where(Question.id.in_(question_ids), Question.status == QuestionStatus.ACTIVE)
        )
        return {question_id: version_id for question_id, version_id in rows.all()}

    async def _versions_by_id(self, version_ids: set[uuid.UUID]) -> dict[uuid.UUID, tuple[Question, QuestionVersion]]:
        if not version_ids:
            return {}
        rows = await self.db.execute(
            select(QuestionVersion, Question)
            .join(Question, Question.id == QuestionVersion.question_id)
            .where(QuestionVersion.id.in_(version_ids))
        )
        return {version.id: (question, version) for version, question in rows.all()}
