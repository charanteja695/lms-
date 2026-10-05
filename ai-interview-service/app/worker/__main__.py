"""python -m app.worker  — outbox relay, event consumer, housekeeping. Scale by running more instances."""

import asyncio
import signal
import sys

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.redis import build_redis
from app.db.session import build_engine, build_sessionmaker
from app.worker.runner import run_forever


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
    try:
        await run_forever(build_sessionmaker(engine), redis, settings, stop)
    finally:
        await redis.aclose()
        await engine.dispose()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(0)
