from app.core.config import Settings
from app.services.rate_limiter import RateLimiter

_WINDOW_SECONDS = 60


async def enforce_run_limits(limiter: RateLimiter, settings: Settings, user_id: int, organization_id: int | None) -> None:
    """Per user, and per institution so one college's exam-week burst cannot starve the others
    (docs/PRODUCT.md §5.2)."""
    await limiter.hit(f"code-run:user:{user_id}", limit=settings.RUN_RATE_LIMIT_PER_USER_PER_MINUTE, window_seconds=_WINDOW_SECONDS)
    if organization_id is not None:
        await limiter.hit(
            f"code-run:org:{organization_id}", limit=settings.RUN_RATE_LIMIT_PER_ORG_PER_MINUTE, window_seconds=_WINDOW_SECONDS
        )


async def enforce_submission_limits(
    limiter: RateLimiter, settings: Settings, user_id: int, organization_id: int | None
) -> None:
    await limiter.hit(
        f"code-submit:user:{user_id}", limit=settings.SUBMISSION_RATE_LIMIT_PER_USER_PER_MINUTE, window_seconds=_WINDOW_SECONDS
    )
    if organization_id is not None:
        await limiter.hit(
            f"code-submit:org:{organization_id}",
            limit=settings.SUBMISSION_RATE_LIMIT_PER_ORG_PER_MINUTE,
            window_seconds=_WINDOW_SECONDS,
        )
