"""The tutor's course-content index (docs/PRODUCT.md §5.5: "Course content RAG")."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, NullableJSONType
from app.domain.enums import JobStatus


class ContentChunk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A passage of a lesson (its notes, a problem statement, or a window of a video transcript) with the vector the
    retriever compares a question against. ``embedding`` is null until the embedding call succeeded; such a chunk is
    still found by the lexical fallback."""

    __tablename__ = "content_chunks"

    version_id: Mapped[int] = mapped_column(BigInteger)
    course_id: Mapped[int] = mapped_column(BigInteger)
    item_id: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[str] = mapped_column(String(12), default="item")  # "item" text or a video "transcript"
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text)
    start_seconds: Mapped[float | None] = mapped_column(Float)  # transcript chunks: where to jump to in the video
    end_seconds: Mapped[float | None] = mapped_column(Float)
    module_title: Mapped[str] = mapped_column(String(200), default="")
    topic_title: Mapped[str] = mapped_column(String(200), default="")
    item_title: Mapped[str] = mapped_column(String(200), default="")
    item_type: Mapped[str] = mapped_column(String(20), default="")
    embedding: Mapped[list[float] | None] = mapped_column(NullableJSONType)
    embedding_model: Mapped[str | None] = mapped_column(String(60))
    retired: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_content_chunks_version", "version_id", "retired"),
        Index("ix_content_chunks_item", "item_id", "source"),
    )


class IndexJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One (re)indexing of a course version, claimed by the worker with a lease (``SKIP LOCKED``), so a dying worker
    loses nothing and two workers never index the same version."""

    __tablename__ = "index_jobs"

    version_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(12), default=JobStatus.PENDING)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime | None]
    lease_until: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(String(500))
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    embedded_count: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    __table_args__ = (UniqueConstraint("version_id", name="uq_index_jobs_version"), Index("ix_index_jobs_due", "status", "next_attempt_at"))
