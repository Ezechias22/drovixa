from __future__ import annotations

import hashlib
from collections.abc import Callable

from fastapi import Request
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.network import client_ip
from app.core.redis import get_redis


def rate_limit(scope: str, *, requests: int, window_seconds: int) -> Callable[[Request], object]:
    async def dependency(request: Request) -> None:
        settings = get_settings()
        if not settings.RATE_LIMIT_ENABLED:
            return
        request_ip = client_ip(request) or "unknown"
        identity = hashlib.sha256(request_ip.encode()).hexdigest()[:24]
        key = f"rate:{scope}:{identity}"
        redis = get_redis()
        try:
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, window_seconds)
            if current > requests:
                retry_after = max(await redis.ttl(key), 1)
                raise AppError(
                    "RATE_LIMITED",
                    "Too many requests. Please try again later.",
                    status_code=429,
                    details={"retry_after_seconds": retry_after},
                )
        except AppError:
            raise
        except RedisError as exc:
            if settings.APP_ENV in {"staging", "production"}:
                raise AppError(
                    "SERVICE_UNAVAILABLE",
                    "The service is temporarily unavailable.",
                    status_code=503,
                ) from exc

    return dependency
