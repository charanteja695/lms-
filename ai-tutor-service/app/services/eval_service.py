"""Offline retrieval evaluation, per course (docs/PRODUCT.md §5.5 "Quality": "Offline evaluation sets run per course").

An author writes questions and names the lesson(s) that answer each. A run asks the retriever the same question a student
would and measures whether the right lesson comes back: hit@k (an expected lesson is in the top k) and MRR. It evaluates the
*retriever* — the part a course's content and chunking control — not the wording of a model's answer, which no offline set
can grade without a judge model; that limit is stated in the README rather than papered over.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.gateway import GatewayClient, GatewayError
from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationFailedError
from app.core.ids import new_public_id
from app.domain.enums import RetrievalMethod
from app.models.evaluation import EvalCase, EvalRun, EvalSet
from app.models.refs import CourseVersionRef, ItemRef
from app.rag.index_cache import IndexCache
from app.rag.similarity import cosine_scores


class EvalService:
    def __init__(self, db: AsyncSession, settings: Settings, gateway: GatewayClient, cache: IndexCache) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway
        self.cache = cache

    async def get_set(self, public_id: int) -> EvalSet:
        found = (await self.db.execute(select(EvalSet).where(EvalSet.public_id == public_id))).scalar_one_or_none()
        if found is None:
            raise NotFoundError("Evaluation set not found.", code="EVAL_SET_NOT_FOUND")
        return found

    async def list_sets(self, course_id: int) -> list[EvalSet]:
        return list((await self.db.execute(select(EvalSet).where(EvalSet.course_id == course_id).order_by(EvalSet.created_at.desc()))).scalars())

    async def create_set(self, *, course_id: int, name: str, created_by: int) -> EvalSet:
        eval_set = EvalSet(public_id=new_public_id(), course_id=course_id, name=name, created_by=created_by)
        self.db.add(eval_set)
        await self.db.commit()
        return eval_set

    async def add_case(self, eval_set: EvalSet, *, question: str, expected_item_ids: list[int]) -> EvalCase:
        known = set((await self.db.execute(select(ItemRef.item_id).where(ItemRef.course_id == eval_set.course_id, ItemRef.item_id.in_(expected_item_ids)))).scalars())
        unknown = [i for i in expected_item_ids if i not in known]
        if unknown:
            raise ValidationFailedError(f"Not lessons of this course: {', '.join(str(i) for i in unknown)}.", code="UNKNOWN_ITEM")
        case = EvalCase(public_id=new_public_id(), eval_set_id=eval_set.id, question=question, expected_item_ids=[str(i) for i in expected_item_ids])
        self.db.add(case)
        await self.db.commit()
        return case

    async def cases(self, eval_set: EvalSet) -> list[EvalCase]:
        return list((await self.db.execute(select(EvalCase).where(EvalCase.eval_set_id == eval_set.id).order_by(EvalCase.created_at, EvalCase.id))).scalars())

    async def runs(self, eval_set: EvalSet) -> list[EvalRun]:
        return list((await self.db.execute(select(EvalRun).where(EvalRun.eval_set_id == eval_set.id).order_by(EvalRun.created_at.desc()))).scalars())

    async def get_run(self, public_id: int) -> EvalRun:
        run = (await self.db.execute(select(EvalRun).where(EvalRun.public_id == public_id))).scalar_one_or_none()
        if run is None:
            raise NotFoundError("Evaluation run not found.", code="EVAL_RUN_NOT_FOUND")
        return run

    async def run(self, eval_set: EvalSet, *, version_id: int | None, triggered_by: int, top_k: int | None = None) -> EvalRun:
        cases = await self.cases(eval_set)
        if not cases:
            raise ConflictError("Add at least one question first.", code="EMPTY_EVAL_SET")
        if version_id is None:
            latest = (
                await self.db.execute(
                    select(CourseVersionRef).where(CourseVersionRef.course_id == eval_set.course_id, CourseVersionRef.retired.is_(False)).order_by(CourseVersionRef.updated_at.desc()).limit(1)
                )
            ).scalar_one_or_none()
            if latest is None:
                raise NotFoundError("This course has no published version indexed yet.", code="COURSE_NOT_INDEXED")
            version_id = latest.version_id
        else:
            ref = await self.db.get(CourseVersionRef, version_id)
            if ref is None or ref.course_id != eval_set.course_id:
                raise ValidationFailedError("That version does not belong to this course.", code="VERSION_NOT_IN_COURSE")
        index = await self.cache.get(self.db, version_id)
        await self.db.commit()  # no transaction across the embedding call
        questions = [c.question for c in cases]
        vectors: list[list[float]] | None = None
        try:
            vectors = (await self.gateway.embed(organization_id=self.settings.PLATFORM_ORGANIZATION_ID, user_id=None, texts=questions)).vectors
        except GatewayError:
            vectors = None
        dense = vectors is not None and len(vectors) == len(cases) and index.matrix.shape[0] > 0
        k = top_k or self.settings.RETRIEVAL_TOP_K
        results: list[dict[str, Any]] = []
        hits, reciprocal = 0, 0.0
        for position, case in enumerate(cases):
            if dense and vectors is not None:
                row_scores = cosine_scores(vectors[position], index.matrix)
                chunk_scores = {index.matrix_rows[row]: float(row_scores[row]) for row in range(len(index.matrix_rows))}
            else:
                lexical = index.lexical.scores(case.question)
                chunk_scores = {i: float(lexical[i]) for i in range(len(index.chunks))}
            best: dict[int, float] = {}
            for chunk_index, score in chunk_scores.items():
                item_id = index.chunks[chunk_index].item_id
                best[item_id] = max(best.get(item_id, float("-inf")), score)
            ranking = sorted(best.items(), key=lambda pair: (-pair[1], pair[0]))
            expected = {int(i) for i in case.expected_item_ids}
            rank = next((n for n, (item_id, _) in enumerate(ranking, start=1) if item_id in expected), None)
            hit = rank is not None and rank <= k
            hits += int(hit)
            reciprocal += 1 / rank if rank else 0.0
            titles = {c.item_id: c.item_title for c in index.chunks}
            results.append(
                {
                    "case_id": str(case.public_id), "question": case.question, "expected_item_ids": case.expected_item_ids, "rank": rank, "hit": hit,
                    "top": [{"item_id": str(item_id), "item_title": titles.get(item_id, ""), "score": round(score, 3)} for item_id, score in ranking[:k]],
                }
            )
        run = EvalRun(
            public_id=new_public_id(), eval_set_id=eval_set.id, version_id=version_id, method=(RetrievalMethod.DENSE if dense else RetrievalMethod.LEXICAL).value,
            top_k=k, case_count=len(cases), hits=hits, hit_rate=round(hits / len(cases), 4), mrr=round(reciprocal / len(cases), 4), results=results, triggered_by=triggered_by,
        )
        self.db.add(run)
        await self.db.commit()
        return run
