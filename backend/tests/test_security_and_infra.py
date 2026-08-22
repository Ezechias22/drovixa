from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import Request
from httpx import AsyncClient
from pydantic import ValidationError
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import redis as redis_module
from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.rate_limit import rate_limit
from app.integrations.videos import factory as video_factory
from app.integrations.videos.cloudflare import CloudflareStreamProvider
from app.integrations.videos.mux import MuxVideoProvider
from app.services import configuration
from app.workers.celery_app import ping


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.counts: dict[str, int] = {}
        self.closed = False

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, **_: Any) -> None:
        self.values[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.values.pop(key, None)

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, _: str, __: int) -> None:
        return None

    async def ttl(self, _: str) -> int:
        return 42

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        self.closed = True


def request_from(ip: str = "10.0.0.1") -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/login",
            "headers": [],
            "client": (ip, 1234),
        }
    )


def test_production_settings_reject_weak_or_shared_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_ENV="production",
            JWT_SECRET="change-me",
            REFRESH_SECRET="change-me",
        )
    strong = Settings(
        _env_file=None,
        APP_ENV="production",
        JWT_SECRET="a" * 40,
        REFRESH_SECRET="b" * 40,
        DEBUG=False,
        VIDEO_PROVIDER="cloudflare_stream",
        BACKEND_CORS_ORIGINS=["https://app.drovixa.example"],
        TRUSTED_HOSTS=["api.drovixa.example"],
        FORCE_HTTPS=True,
        METRICS_TOKEN="m" * 32,
    )
    assert strong.docs_enabled is False
    with pytest.raises(ValidationError, match="must be different"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            JWT_SECRET="a" * 40,
            REFRESH_SECRET="a" * 40,
            DEBUG=False,
            VIDEO_PROVIDER="cloudflare_stream",
        )
    with pytest.raises(ValidationError, match="DEBUG must be false"):
        Settings(
            _env_file=None,
            APP_ENV="staging",
            JWT_SECRET="a" * 40,
            REFRESH_SECRET="b" * 40,
            DEBUG=True,
            VIDEO_PROVIDER="cloudflare_stream",
            BACKEND_CORS_ORIGINS=["https://app.drovixa.example"],
            TRUSTED_HOSTS=["api.drovixa.example"],
            FORCE_HTTPS=True,
            METRICS_TOKEN="m" * 32,
        )


def test_production_settings_reject_wildcard_origins() -> None:
    with pytest.raises(ValidationError, match="Wildcard CORS"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            JWT_SECRET="a" * 40,
            REFRESH_SECRET="b" * 40,
            DEBUG=False,
            VIDEO_PROVIDER="cloudflare_stream",
            BACKEND_CORS_ORIGINS=["*"],
            TRUSTED_HOSTS=["api.drovixa.example"],
            FORCE_HTTPS=True,
            METRICS_TOKEN="m" * 32,
        )


async def test_rate_limiter_counts_and_rejects(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: SimpleNamespace(RATE_LIMIT_ENABLED=True, APP_ENV="production"),
    )
    monkeypatch.setattr("app.core.rate_limit.get_redis", lambda: fake)
    limiter = rate_limit("test", requests=1, window_seconds=60)
    await limiter(request_from())
    with pytest.raises(AppError) as error:
        await limiter(request_from())
    assert error.value.code == "RATE_LIMITED"
    assert error.value.details == {"retry_after_seconds": 42}


async def test_runtime_configuration_cache_and_invalidation(
    monkeypatch: pytest.MonkeyPatch, db: AsyncSession
) -> None:
    fake = FakeRedis()
    monkeypatch.setattr(
        configuration,
        "get_settings",
        lambda: SimpleNamespace(APP_ENV="development"),
    )
    monkeypatch.setattr(configuration, "get_redis", lambda: fake)

    first = await configuration.public_feature_flags(db)
    assert first["guest_mode_enabled"]["enabled"] is True
    assert configuration.FEATURE_CACHE_KEY in fake.values

    cached = await configuration.public_feature_flags(db)
    assert cached == first
    await configuration.invalidate_runtime_configuration()
    assert fake.values == {}


async def test_runtime_configuration_cache_failures_are_non_fatal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenRedis:
        async def get(self, _: str) -> str:
            return "not-json"

        async def set(self, *_: Any, **__: Any) -> None:
            raise RedisError("cache unavailable")

        async def delete(self, *_: str) -> None:
            raise RedisError("cache unavailable")

    broken = BrokenRedis()
    monkeypatch.setattr(
        configuration,
        "get_settings",
        lambda: SimpleNamespace(APP_ENV="development"),
    )
    monkeypatch.setattr(configuration, "get_redis", lambda: broken)
    assert await configuration._cache_get("bad-json") is None
    await configuration._cache_set("key", {"value": True})
    await configuration.invalidate_runtime_configuration()


async def test_rate_limiter_handles_redis_outage_by_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenRedis:
        async def incr(self, _: str) -> int:
            raise RedisError("redis unavailable")

    monkeypatch.setattr("app.core.rate_limit.get_redis", lambda: BrokenRedis())
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: SimpleNamespace(RATE_LIMIT_ENABLED=True, APP_ENV="development"),
    )
    await rate_limit("outage", requests=1, window_seconds=60)(request_from())
    monkeypatch.setattr(
        "app.core.rate_limit.get_settings",
        lambda: SimpleNamespace(RATE_LIMIT_ENABLED=True, APP_ENV="production"),
    )
    with pytest.raises(AppError) as error:
        await rate_limit("outage", requests=1, window_seconds=60)(request_from())
    assert error.value.code == "SERVICE_UNAVAILABLE"


def test_redis_and_video_provider_factories(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    redis_module._redis = None
    monkeypatch.setattr(redis_module.Redis, "from_url", lambda *_args, **_kwargs: fake)
    assert redis_module.get_redis() is fake
    assert redis_module.get_redis() is fake

    video_factory.get_video_provider.cache_clear()
    mux_settings = SimpleNamespace(VIDEO_PROVIDER="mux")
    monkeypatch.setattr(video_factory, "get_settings", lambda: mux_settings)
    assert isinstance(video_factory.get_video_provider(), MuxVideoProvider)
    video_factory.get_video_provider.cache_clear()
    cloudflare_settings = SimpleNamespace(VIDEO_PROVIDER="cloudflare_stream")
    monkeypatch.setattr(video_factory, "get_settings", lambda: cloudflare_settings)
    assert isinstance(video_factory.get_video_provider(), CloudflareStreamProvider)
    video_factory.get_video_provider.cache_clear()
    monkeypatch.setattr(
        video_factory,
        "get_settings",
        lambda: SimpleNamespace(VIDEO_PROVIDER="unsupported"),
    )
    with pytest.raises(RuntimeError, match="Unsupported video provider"):
        video_factory.get_video_provider()
    video_factory.get_video_provider.cache_clear()


def test_worker_ping() -> None:
    assert ping() == "pong"


async def test_security_headers_keep_api_strict_and_allow_docs_assets(
    client: AsyncClient,
) -> None:
    docs_response = await client.get("/docs")
    assert docs_response.status_code == 200
    assert "https://cdn.jsdelivr.net" in docs_response.headers["Content-Security-Policy"]
    assert "swagger-ui-bundle.js" in docs_response.text

    api_response = await client.get("/api/v1")
    assert api_response.status_code == 200
    assert (
        api_response.headers["Content-Security-Policy"]
        == "default-src 'none'; frame-ancestors 'none'"
    )


async def test_redis_singleton_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRedis()
    monkeypatch.setattr(redis_module, "_redis", fake)
    await redis_module.close_redis()
    assert fake.closed is True
    assert redis_module._redis is None
