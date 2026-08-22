from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import DbSession
from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.version import build_info
from app.schemas.common import success

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live")
async def liveness() -> dict[str, Any]:
    return success({"status": "ok", "service": "drovixa-api", **build_info()})


@router.get("/ready")
async def readiness(response: Response, db: DbSession) -> dict[str, Any]:
    checks: dict[str, str] = {"database": "down", "redis": "skipped"}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "up"
    except SQLAlchemyError:
        await db.rollback()

    settings = get_settings()
    if settings.APP_ENV != "testing":
        try:
            await get_redis().ping()
            checks["redis"] = "up"
        except RedisError:
            checks["redis"] = "down"

    ready = checks["database"] == "up" and (
        not settings.HEALTHCHECK_REDIS_REQUIRED or checks["redis"] == "up"
    )
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return success({"status": "ready" if ready else "not_ready", "checks": checks, **build_info()})
