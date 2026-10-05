"""python -m app.worker  — export jobs, event relay and housekeeping. Scale by running more instances."""

import asyncio
import signal
import sys

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.redis import build_redis
from app.db.session import build_engine, build_sessionmaker
from app.notifications.email import build_email_sender
from app.worker.runner import WorkerContext, run_forever


async def main() -> int:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL, settings.LOG_JSON)
    engine = build_engine(settings)
    redis = build_redis(settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows: Ctrl+C raises KeyboardInterrupt instead
            pass
    ctx = WorkerContext(
        settings=settings,
        sessionmaker=build_sessionmaker(engine),
        redis=redis,
        email_sender=build_email_sender(settings),
    )
    try:
        await run_forever(ctx, stop)
    finally:
        await redis.aclose()
        await engine.dispose()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
