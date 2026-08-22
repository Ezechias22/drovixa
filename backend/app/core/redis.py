from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_timeout=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            health_check_interval=30,
            retry_on_timeout=True,
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
