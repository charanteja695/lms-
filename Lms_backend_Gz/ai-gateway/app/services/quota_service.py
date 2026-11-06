"""Per-org token/request/budget quota (docs/PRODUCT.md §6: "quotas & cost per org").

**Reserve, call, adjust — never hold the DB open across the provider call** (the same lesson proctoring-service's
analyzer integration learned the hard way): ``reserve()`` commits before the caller does anything slow, and
``adjust()``/``refund()`` open a fresh transaction afterwards. ``reserve()`` locks the org's usage row with
``SELECT ... FOR UPDATE`` so two concurrent calls from the same org cannot both squeeze under the limit — proven in
tests/integration/test_postgres.py.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import PermissionDeniedError, QuotaExceededError
from app.core.time import period_of, utcnow
from app.models.quota import OrgQuota, OrgUsage


@dataclass(frozen=True, slots=True)
class Limits:
    token_limit: int
    request_limit: int
    budget_cents: int
    enabled: bool


@dataclass(frozen=True, slots=True)
class Reservation:
    organization_id: int
    period: str
    estimated_tokens: int


async def _limits(db: AsyncSession, settings: Settings, organization_id: int) -> Limits:
    quota = await db.get(OrgQuota, organization_id)
    if quota is None:
        return Limits(settings.DEFAULT_MONTHLY_TOKEN_LIMIT, settings.DEFAULT_MONTHLY_REQUEST_LIMIT, settings.DEFAULT_MONTHLY_BUDGET_CENTS, True)
    return Limits(
        quota.monthly_token_limit if quota.monthly_token_limit is not None else settings.DEFAULT_MONTHLY_TOKEN_LIMIT,
        quota.monthly_request_limit if quota.monthly_request_limit is not None else settings.DEFAULT_MONTHLY_REQUEST_LIMIT,
        quota.monthly_budget_cents if quota.monthly_budget_cents is not None else settings.DEFAULT_MONTHLY_BUDGET_CENTS,
        quota.enabled,
    )


class QuotaService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    async def _select_locked(self, organization_id: int, period: str) -> OrgUsage | None:
        return (
            await self.db.execute(
                select(OrgUsage).where(OrgUsage.organization_id == organization_id, OrgUsage.period == period).with_for_update()
            )
        ).scalar_one_or_none()

    async def _usage_row_locked(self, organization_id: int, period: str) -> OrgUsage:
        row = await self._select_locked(organization_id, period)
        if row is not None:
            return row
        # No row yet for this org+period. A savepoint, not the whole transaction: if a concurrent caller's
        # insert for the same org+period commits first, ours fails the unique constraint, and we fall back to
        # locking the row it created instead of poisoning this transaction.
        try:
            async with self.db.begin_nested():
                row = OrgUsage(organization_id=organization_id, period=period)
                self.db.add(row)
                await self.db.flush()
            return row
        except IntegrityError:
            row = await self._select_locked(organization_id, period)
            assert row is not None  # the conflicting insert just committed; the row must exist now
            return row

    async def reserve(self, *, organization_id: int, estimated_tokens: int) -> Reservation:
        """Commits on return: the reservation is durable before any slow provider call starts."""
        limits = await _limits(self.db, self.settings, organization_id)
        if not limits.enabled:
            raise PermissionDeniedError("AI usage is disabled for this organization.", code="AI_DISABLED")
        period = period_of(utcnow())
        usage = await self._usage_row_locked(organization_id, period)
        if usage.requests_used + 1 > limits.request_limit:
            raise QuotaExceededError("The monthly request quota is exhausted.", code="REQUEST_QUOTA_EXCEEDED")
        total_tokens = usage.prompt_tokens_used + usage.completion_tokens_used
        if total_tokens + estimated_tokens > limits.token_limit:
            raise QuotaExceededError("The monthly token quota is exhausted.", code="TOKEN_QUOTA_EXCEEDED")
        if usage.cost_cents_used >= limits.budget_cents:
            raise QuotaExceededError("The monthly budget is exhausted.", code="BUDGET_QUOTA_EXCEEDED")
        usage.requests_used += 1
        usage.completion_tokens_used += estimated_tokens  # refined in adjust() once the actual usage is known
        await self.db.commit()
        return Reservation(organization_id=organization_id, period=period, estimated_tokens=estimated_tokens)

    async def adjust(self, reservation: Reservation, *, prompt_tokens: int, completion_tokens: int, cost_cents: int) -> None:
        """Replace the estimate with what actually happened. Opens and commits its own transaction."""
        usage = await self._usage_row_locked(reservation.organization_id, reservation.period)
        usage.completion_tokens_used += completion_tokens - reservation.estimated_tokens
        usage.prompt_tokens_used += prompt_tokens
        usage.cost_cents_used += cost_cents
        await self.db.commit()

    async def refund(self, reservation: Reservation) -> None:
        """The call never reached a provider that could report usage (every provider failed): give the
        estimated tokens back so a string of failures doesn't itself exhaust the quota."""
        usage = await self._usage_row_locked(reservation.organization_id, reservation.period)
        usage.completion_tokens_used -= reservation.estimated_tokens
        await self.db.commit()

    async def usage(self, organization_id: int, period: str) -> tuple[OrgUsage | None, Limits]:
        limits = await _limits(self.db, self.settings, organization_id)
        row = (
            await self.db.execute(select(OrgUsage).where(OrgUsage.organization_id == organization_id, OrgUsage.period == period))
        ).scalar_one_or_none()
        return row, limits
