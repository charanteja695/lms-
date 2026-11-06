from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.core.exceptions import ConflictError


def build_engine(settings: Settings) -> AsyncEngine:
    url = make_url(settings.DATABASE_URL)
    kwargs: dict[str, Any] = {"echo": settings.DB_ECHO, "pool_pre_ping": True}
    is_sqlite = url.get_backend_name() == "sqlite"
    if is_sqlite:
        kwargs.update(poolclass=StaticPool, connect_args={"check_same_thread": False})
    else:
        kwargs.update(
            connect_args={
                "server_settings": {
                    "statement_timeout": str(settings.DB_STATEMENT_TIMEOUT_MS),
                    "idle_in_transaction_session_timeout": str(max(settings.DB_STATEMENT_TIMEOUT_MS * 4, 60_000)),
                    "application_name": settings.APP_NAME,
                }
            },
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
            pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
        )
    engine = create_async_engine(url, **kwargs)

    if is_sqlite:

        @event.listens_for(engine.sync_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection: Any, _: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def build_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


_CONFLICT_MESSAGE = "The request conflicts with existing data"


async def commit_or_conflict(db: AsyncSession, message: str = _CONFLICT_MESSAGE) -> None:
    """Commit, translating unique-constraint races into a 409 instead of a 500."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(message) from exc


async def flush_or_conflict(db: AsyncSession, message: str = _CONFLICT_MESSAGE) -> None:
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError(message) from exc
