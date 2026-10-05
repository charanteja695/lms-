"""Per-org quota configuration and usage (docs/PRODUCT.md §6, `ai-gateway` row: "quotas & cost per org").

An org without an ``OrgQuota`` row uses the platform defaults in ``Settings`` (see app/services/quota_service.py).
``OrgUsage`` has one row per org per calendar-month period, incremented under ``SELECT ... FOR UPDATE`` so
concurrent calls from the same org cannot together spend past the limit (verified in tests/integration/test_postgres.py).
"""

from sqlalchemy import BigInteger, Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class OrgQuota(TimestampMixin, Base):
    __tablename__ = "org_quotas"

    organization_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    monthly_token_limit: Mapped[int | None] = mapped_column(Integer)
    monthly_request_limit: Mapped[int | None] = mapped_column(Integer)
    monthly_budget_cents: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # an admin kill switch, independent of the limits
    updated_by: Mapped[int | None] = mapped_column(BigInteger)


class OrgUsage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "org_usage"

    organization_id: Mapped[int] = mapped_column(BigInteger)
    period: Mapped[str] = mapped_column(String(7))  # "YYYY-MM"
    requests_used: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    cost_cents_used: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (UniqueConstraint("organization_id", "period", name="uq_org_usage_org_period"),)
