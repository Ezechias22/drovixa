from __future__ import annotations

import json
import logging
from typing import Any

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis
from app.models.configuration import FeatureFlag, RemoteConfig

logger = logging.getLogger(__name__)
FEATURE_CACHE_KEY = "drovixa:feature-flags:v1"
REMOTE_CACHE_KEY = "drovixa:remote-config:v1"


async def _cache_get(key: str) -> Any | None:
    if get_settings().APP_ENV == "testing":
        return None
    try:
        value = await get_redis().get(key)
        return json.loads(value) if value else None
    except (RedisError, json.JSONDecodeError):
        logger.warning("cache_read_failed", extra={"cache_key": key})
        return None


async def _cache_set(key: str, value: Any) -> None:
    if get_settings().APP_ENV == "testing":
        return
    try:
        await get_redis().set(key, json.dumps(value), ex=60)
    except RedisError:
        logger.warning("cache_write_failed", extra={"cache_key": key})


async def invalidate_runtime_configuration() -> None:
    if get_settings().APP_ENV == "testing":
        return
    try:
        await get_redis().delete(FEATURE_CACHE_KEY, REMOTE_CACHE_KEY)
    except RedisError:
        logger.warning("cache_invalidation_failed")


async def public_feature_flags(db: AsyncSession) -> dict[str, Any]:
    cached = await _cache_get(FEATURE_CACHE_KEY)
    if isinstance(cached, dict):
        return cached
    rows = (await db.scalars(select(FeatureFlag).order_by(FeatureFlag.key))).all()
    result = {
        row.key: {
            "enabled": row.enabled,
            "rollout_percentage": row.rollout_percentage,
            "rules": row.rules,
        }
        for row in rows
    }
    await _cache_set(FEATURE_CACHE_KEY, result)
    return result


async def public_remote_config(db: AsyncSession) -> dict[str, Any]:
    cached = await _cache_get(REMOTE_CACHE_KEY)
    if isinstance(cached, dict):
        return cached
    rows = (
        await db.scalars(
            select(RemoteConfig).where(RemoteConfig.is_public.is_(True)).order_by(RemoteConfig.key)
        )
    ).all()
    result = {row.key: row.value for row in rows}
    await _cache_set(REMOTE_CACHE_KEY, result)
    return result
