"""Finding what to answer from: course passages (RAG) and curated FAQ entries.

Dense (embedding) retrieval is the normal path. If the embedding call is unavailable the tutor falls back to word overlap
rather than refusing to answer — the retrieval method used is recorded on every answer so the difference is visible.
Quota exhaustion and a disabled organization are *not* swallowed: they mean the caller may not spend AI at all.
"""

from dataclasses import dataclass

import numpy as np
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.gateway import GatewayClient, GatewayUnavailable
from app.core.config import Settings
from app.domain.enums import FaqStatus, RetrievalMethod
from app.models.faq import FaqEntry
from app.rag.index_cache import ChunkMeta, IndexCache
from app.rag.similarity import LexicalIndex, cosine_scores, normalize_rows, top_k

OPEN_LESSON_SCORE = 0.5  # the score shown for a passage that is there because the student had its lesson open, not because it ranked


@dataclass(frozen=True, slots=True)
class Passage:
    chunk: ChunkMeta
    score: float


@dataclass(frozen=True, slots=True)
class Retrieval:
    passages: list[Passage]
    method: RetrievalMethod
    top_score: float  # the best score seen, before the relevance floor, for the low-confidence decision


@dataclass(frozen=True, slots=True)
class FaqHit:
    entry: FaqEntry
    score: float


class RetrievalService:
    def __init__(self, db: AsyncSession, settings: Settings, gateway: GatewayClient, cache: IndexCache) -> None:
        self.db = db
        self.settings = settings
        self.gateway = gateway
        self.cache = cache

    async def embed_query(self, *, organization_id: int, user_id: int | None, text: str) -> list[float] | None:
        try:
            result = await self.gateway.embed(organization_id=organization_id, user_id=user_id, texts=[text])
        except GatewayUnavailable:
            return None
        return result.vectors[0] if result.vectors else None

    async def search_content(self, version_id: int, query: str, vector: list[float] | None, *, k: int | None = None) -> Retrieval:
        k = k or self.settings.RETRIEVAL_TOP_K
        index = await self.cache.get(self.db, version_id)
        if not index.chunks:
            return Retrieval([], RetrievalMethod.NONE, 0.0)
        ranked: list[tuple[int, float]] = []
        method = RetrievalMethod.LEXICAL
        if vector is not None and index.matrix.shape[0] > 0:
            scores = cosine_scores(vector, index.matrix)
            dense = [(index.matrix_rows[row], score) for row, score in top_k(scores, k)]
            if dense and dense[0][1] > 0:
                ranked, method = dense, RetrievalMethod.DENSE
        if not ranked:
            ranked = top_k(index.lexical.scores(query), k)
        top_score = ranked[0][1] if ranked else 0.0
        passages = [Passage(index.chunks[i], score) for i, score in ranked if score >= self.settings.MIN_RELEVANCE]
        return Retrieval(passages, method, top_score)

    async def with_open_lesson(self, retrieval: Retrieval, version_id: int, item_id: int, *, limit: int = 2) -> Retrieval:
        """Add the lesson the student has open (its first passages) to what was retrieved, if it is not already there: a
        question about "this problem" rarely shares words with the problem statement, but it is what they are asking about."""
        index = await self.cache.get(self.db, version_id)
        have = {p.chunk.chunk_id for p in retrieval.passages}
        extra = [Passage(c, OPEN_LESSON_SCORE) for c in index.chunks if c.item_id == item_id and c.chunk_id not in have][:limit]
        if not extra:
            return retrieval
        return Retrieval([*retrieval.passages, *extra], retrieval.method, retrieval.top_score)

    async def search_faq(self, *, organization_id: int | None, course_id: int | None, query: str, vector: list[float] | None) -> FaqHit | None:
        scope = or_(FaqEntry.scope == "platform")
        if organization_id is not None:
            scope = or_(scope, (FaqEntry.scope == "organization") & (FaqEntry.organization_id == organization_id))
        if course_id is not None:
            scope = or_(scope, (FaqEntry.scope == "course") & (FaqEntry.course_id == course_id))
        entries = list((await self.db.execute(select(FaqEntry).where(FaqEntry.status == FaqStatus.PUBLISHED, scope).order_by(FaqEntry.created_at))).scalars())
        if not entries:
            return None
        lexical = LexicalIndex([e.question for e in entries]).scores(query)
        best: FaqHit | None = None
        for position, entry in enumerate(entries):
            score = float(lexical[position])
            if vector is not None and entry.embedding and len(entry.embedding) == len(vector):
                dense = float(cosine_scores(vector, normalize_rows(np.asarray([entry.embedding], dtype=np.float32)))[0])
                score = max(dense, 0.0)  # with a comparable vector, the dense score replaces the word-overlap one
            if best is None or score > best.score:
                best = FaqHit(entry, score)
        return best
