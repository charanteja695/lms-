from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, Float, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.types import JSONType

# A row with no organisation or employer (a platform-wide event, e.g. `course.published`) is stored as 0,
# never NULL: PostgreSQL treats NULL as distinct from NULL in a unique index, which would let two rollup
# runs for the same "no organisation" bucket silently duplicate instead of colliding as intended.
NONE_ORG = 0
NONE_DIM = ""


class EventFact(UUIDPrimaryKeyMixin, Base):
    """One row per ingested event (docs/PRODUCT.md §5.9): the plain columns a dashboard query filters and
    sums on, plus the original payload for anyone who needs to see exactly what produced a number. Never
    written to directly by app code — only by app/ingest (see app/ingest/extract.py for what is extracted
    from which event type, and why some events need `EnrollmentRef` to know their organisation)."""

    __tablename__ = "event_facts"

    event_id: Mapped[str] = mapped_column(String(64), unique=True)
    event_type: Mapped[str] = mapped_column(String(100))
    occurred_at: Mapped[datetime]
    organization_id: Mapped[int] = mapped_column(BigInteger, default=NONE_ORG)
    employer_id: Mapped[int] = mapped_column(BigInteger, default=NONE_ORG)
    dim_key: Mapped[str] = mapped_column(String(30), default=NONE_DIM)
    dim_value: Mapped[str] = mapped_column(String(60), default=NONE_DIM)
    measure_a: Mapped[float | None] = mapped_column(Float)
    measure_b: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType)
    ingested_at: Mapped[datetime]

    __table_args__ = (
        Index("ix_event_facts_type_org_day", "event_type", "organization_id", "occurred_at"),
        Index("ix_event_facts_type_employer_day", "event_type", "employer_id", "occurred_at"),
    )


class DailyRollup(Base):
    """One row per (event type, organisation, employer, dimension, day): a sum of that day's `EventFact`
    rows, recomputed from scratch whenever the worker revisits a day (never patched in place) — see
    app/aggregations/rollup.py. Cheap to rebuild from `EventFact`, so a bug fix or a new dashboard replays
    history instead of needing a backfill migration."""

    __tablename__ = "daily_rollups"

    event_type: Mapped[str] = mapped_column(String(100), primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=NONE_ORG)
    employer_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=NONE_ORG)
    dim_key: Mapped[str] = mapped_column(String(30), primary_key=True, default=NONE_DIM)
    dim_value: Mapped[str] = mapped_column(String(60), primary_key=True, default=NONE_DIM)
    day: Mapped[date] = mapped_column(primary_key=True)
    count: Mapped[int] = mapped_column(default=0)
    sum_a: Mapped[float] = mapped_column(Float, default=0.0)
    sum_b: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (Index("ix_daily_rollups_lookup", "event_type", "organization_id", "employer_id", "day"),)


class EnrollmentRef(Base):
    """learning-service's enrolment id -> its organisation and student, from `enrollment.created`. Several
    learning events (`topic.completed`, `module.completed`, `course.eligible_for_final`, `course.passed`,
    `course.failed`, `course.pass_revoked`) carry only an `enrollment_id`, not an organisation — this is
    the local read-model that resolves one to the other, the same "consume the event, build a read-model"
    pattern every service here uses instead of a synchronous call."""

    __tablename__ = "enrollment_refs"

    enrollment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    organization_id: Mapped[int] = mapped_column(BigInteger, default=NONE_ORG)
    student_user_id: Mapped[int] = mapped_column(BigInteger)
