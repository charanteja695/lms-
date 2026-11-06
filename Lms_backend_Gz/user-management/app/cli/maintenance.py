"""Housekeeping jobs. Run ``python -m app.cli purge-expired`` daily (cron / Kubernetes CronJob).

Deletes in small batches with a commit per batch, so it never holds long locks on busy tables.
"""

from datetime import timedelta
from typing import Any

from sqlalchemy import ColumnElement, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.time import utcnow
from app.db.session import build_engine, build_sessionmaker
from app.models import MfaChallenge, OutboxEvent, PasswordResetRequest, RefreshToken, UserSession


def _purge_jobs(settings: Settings) -> list[tuple[str, Any, ColumnElement[bool]]]:
    now = utcnow()
    retention_cutoff = now - timedelta(days=settings.SESSION_RETENTION_DAYS)
    return [
        (
            "refresh_tokens",
            RefreshToken,
            or_(RefreshToken.expires_at < now, RefreshToken.used_at < retention_cutoff),
        ),
        (
            "user_sessions",
            UserSession,
            or_(UserSession.expires_at < retention_cutoff, UserSession.revoked_at < retention_cutoff),
        ),
        (
            "password_reset_requests",
            PasswordResetRequest,
            or_(
                PasswordResetRequest.expires_at < retention_cutoff, PasswordResetRequest.consumed_at < retention_cutoff
            ),
        ),
        ("mfa_challenges", MfaChallenge, MfaChallenge.expires_at < now - timedelta(days=1)),
        (
            "outbox_events",
            OutboxEvent,
            OutboxEvent.published_at < now - timedelta(days=settings.OUTBOX_RETENTION_DAYS),
        ),
    ]


async def purge_expired(
    settings: Settings,
    *,
    sessionmaker: async_sessionmaker[AsyncSession] | None = None,
    batch_size: int = 5_000,
) -> dict[str, int]:
    engine = None
    if sessionmaker is None:
        engine = build_engine(settings)
        sessionmaker = build_sessionmaker(engine)
    totals: dict[str, int] = {}
    try:
        for name, model, condition in _purge_jobs(settings):
            deleted = 0
            while True:
                async with sessionmaker() as db:
                    ids = list((await db.execute(select(model.id).where(condition).limit(batch_size))).scalars())
                    if not ids:
                        break
                    await db.execute(delete(model).where(model.id.in_(ids)))
                    await db.commit()
                deleted += len(ids)
            totals[name] = deleted
    finally:
        if engine is not None:
            await engine.dispose()
    return totals
