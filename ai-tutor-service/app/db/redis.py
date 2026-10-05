from redis.asyncio import Redis

from app.core.config import Settings


def build_redis(settings: Settings) -> Redis:
    return Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_timeout=2,
        socket_connect_timeout=2,
        health_check_interval=30,
    )
