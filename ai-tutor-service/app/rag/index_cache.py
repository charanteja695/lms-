"""An in-process, per-version copy of the content index, ready to score a question against.

Loading a version's chunks and building a normalised matrix is the expensive part of a retrieval, so it is done once per
process and reused until the version's chunks change (a cheap ``count`` / ``max(updated_at)`` probe decides). The cache is
bounded (least recently used version out), and every process rebuilds its own — nothing here is shared or authoritative.
"""

from collections import OrderedDict
from dataclasses import dataclass

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import ContentChunk
from app.rag.similarity import LexicalIndex, normalize_rows


@dataclass(frozen=True, slots=True)
class ChunkMeta:
    chunk_id: str
    item_id: int
    item_title: str
    topic_title: str
    module_title: str
    item_type: str
    source: str
    text: str
    start_seconds: float | None
    end_seconds: float | None


@dataclass(slots=True)
class VersionIndex:
    signature: tuple[int, str]
    chunks: list[ChunkMeta]
    matrix: np.ndarray  # one row per embedded chunk, length-normalised
    matrix_rows: list[int]  # which chunk each matrix row belongs to
    lexical: LexicalIndex


class IndexCache:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self._items: OrderedDict[int, VersionIndex] = OrderedDict()

    def clear(self) -> None:
        self._items.clear()

    async def get(self, db: AsyncSession, version_id: int) -> VersionIndex:
        count, newest = (
            await db.execute(
                select(func.count(ContentChunk.id), func.max(ContentChunk.updated_at)).where(ContentChunk.version_id == version_id, ContentChunk.retired.is_(False))
            )
        ).one()
        signature = (int(count), str(newest))
        cached = self._items.get(version_id)
        if cached is not None and cached.signature == signature:
            self._items.move_to_end(version_id)
            return cached
        index = await self._build(db, version_id, signature)
        self._items[version_id] = index
        self._items.move_to_end(version_id)
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)
        return index

    async def _build(self, db: AsyncSession, version_id: int, signature: tuple[int, str]) -> VersionIndex:
        rows = (
            (
                await db.execute(
                    select(ContentChunk)
                    .where(ContentChunk.version_id == version_id, ContentChunk.retired.is_(False))
                    .order_by(ContentChunk.item_id, ContentChunk.source, ContentChunk.chunk_index)
                )
            )
            .scalars()
            .all()
        )
        chunks = [
            ChunkMeta(str(r.id), r.item_id, r.item_title, r.topic_title, r.module_title, r.item_type, r.source, r.text, r.start_seconds, r.end_seconds)
            for r in rows
        ]
        vectors: list[list[float]] = []
        positions: list[int] = []
        dimension: int | None = None
        for position, row in enumerate(rows):
            if not row.embedding:
                continue
            dimension = dimension or len(row.embedding)
            if len(row.embedding) == dimension:  # a chunk embedded by a different model has another size: left to the lexical path
                vectors.append(row.embedding)
                positions.append(position)
        matrix = normalize_rows(np.asarray(vectors, dtype=np.float32)) if vectors else np.zeros((0, 0), dtype=np.float32)
        return VersionIndex(signature, chunks, matrix, positions, LexicalIndex([c.text for c in chunks]))
