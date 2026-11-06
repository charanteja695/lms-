"""Offline evaluation sets, run per course (docs/PRODUCT.md §5.5 "Quality")."""

from typing import Any

from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType


class EvalSet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "eval_sets"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    course_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(120))
    created_by: Mapped[int] = mapped_column(BigInteger)

    __table_args__ = (Index("ix_eval_sets_course", "course_id"),)


class EvalCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A question a good tutor must answer from the right lesson: the items whose text contains the answer."""

    __tablename__ = "eval_cases"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    eval_set_id: Mapped[Any] = mapped_column(ForeignKey("eval_sets.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(String(500))
    expected_item_ids: Mapped[list[str]] = mapped_column(JSONType, default=list)


class EvalRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A retrieval evaluation of one set against one version: hit@k (an expected item is among the top-k) and MRR."""

    __tablename__ = "eval_runs"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    eval_set_id: Mapped[Any] = mapped_column(ForeignKey("eval_sets.id", ondelete="CASCADE"))
    version_id: Mapped[int] = mapped_column(BigInteger)
    method: Mapped[str] = mapped_column(String(10))
    top_k: Mapped[int] = mapped_column(Integer)
    case_count: Mapped[int] = mapped_column(Integer, default=0)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    mrr: Mapped[float] = mapped_column(Float, default=0.0)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    triggered_by: Mapped[int] = mapped_column(BigInteger)
