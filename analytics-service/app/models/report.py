from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, NullableJSONType
from app.domain.enums import ReportFormat, ReportFrequency, ReportStatus


class ReportDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A saved dashboard + filters + a schedule (docs/PRODUCT.md §5.9 "Scheduled reports"). The worker runs
    it when due and renders a `ReportRun`; running it does not change what the dashboard itself shows."""

    __tablename__ = "report_definitions"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    owner_user_id: Mapped[int] = mapped_column(BigInteger)
    organization_id: Mapped[int | None] = mapped_column(BigInteger)  # null: a platform-wide report
    name: Mapped[str] = mapped_column(String(160))
    dashboard: Mapped[str] = mapped_column(String(20))
    filters: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)  # {days: int, dim_key?, dim_value?}
    format: Mapped[str] = mapped_column(String(6), default=ReportFormat.CSV)
    frequency: Mapped[str] = mapped_column(String(10), default=ReportFrequency.WEEKLY)
    next_run_at: Mapped[datetime]
    active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (Index("ix_report_definitions_due", "active", "next_run_at"),)


class ReportRun(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """One rendering of a `ReportDefinition`. The content is kept here, not in object storage: fine at this
    volume (a handful of rows and small CSVs per definition), a known limit at real scale (see README)."""

    __tablename__ = "report_runs"

    public_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    definition_id: Mapped[Any] = mapped_column(ForeignKey("report_definitions.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(8), default=ReportStatus.PENDING)
    period_start: Mapped[date | None]
    period_end: Mapped[date | None]
    row_count: Mapped[int | None]
    content: Mapped[bytes | None] = mapped_column(LargeBinary)
    content_type: Mapped[str | None] = mapped_column(String(60))
    error: Mapped[str | None] = mapped_column(Text)
    dashboard_snapshot: Mapped[dict[str, Any] | None] = mapped_column(NullableJSONType)  # the rows rendered, for GET without re-parsing the CSV
    generated_at: Mapped[datetime | None]

    __table_args__ = (Index("ix_report_runs_definition", "definition_id", "created_at"),)
