from types import SimpleNamespace

import pytest
from httpx import AsyncClient


async def test_liveness_readiness_and_security_headers(client: AsyncClient) -> None:
    root = await client.get("/api/v1")
    assert root.status_code == 200
    assert root.json()["data"]["app"] == "Drovixa"
    assert root.json()["data"]["version"] == "0.11.0"

    live = await client.get("/api/v1/health/live")
    assert live.status_code == 200
    assert live.json()["data"]["status"] == "ok"
    assert live.json()["data"]["version"] == "0.11.0"
    assert live.headers["x-content-type-options"] == "nosniff"
    assert live.headers["x-request-id"]

    ready = await client.get("/api/v1/health/ready")
    assert ready.status_code == 200
    assert ready.json()["data"]["checks"] == {"database": "up", "redis": "skipped"}


async def test_readiness_checks_required_redis(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class HealthyRedis:
        async def ping(self) -> bool:
            return True

    monkeypatch.setattr(
        "app.routes.health.get_settings",
        lambda: SimpleNamespace(APP_ENV="production", HEALTHCHECK_REDIS_REQUIRED=True),
    )
    monkeypatch.setattr("app.routes.health.get_redis", lambda: HealthyRedis())
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["data"]["checks"]["redis"] == "up"


async def test_public_runtime_configuration_excludes_private_values(client: AsyncClient) -> None:
    flags = await client.get("/api/v1/feature-flags")
    assert flags.status_code == 200
    assert flags.json()["data"]["guest_mode_enabled"]["enabled"] is True
    assert flags.json()["data"]["comments_enabled"]["enabled"] is False

    config = await client.get("/api/v1/remote-config")
    assert config.status_code == 200
    assert config.json()["data"] == {"accent_color": "#FF3D71"}


async def test_standard_not_found_error(client: AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["request_id"]


async def test_metrics_and_request_size_protection(client: AsyncClient) -> None:
    await client.get("/api/v1/health/live")
    metrics = await client.get("/api/v1/metrics")
    assert metrics.status_code == 200
    assert "drovixa_http_requests_total" in metrics.text

    too_large = await client.post(
        "/api/v1/auth/login",
        headers={"Content-Length": "999999999"},
        content=b"{}",
    )
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"

    async def oversized_chunks():
        yield b"x" * 1_100_000
        yield b"y" * 1_100_000

    chunked = await client.post("/api/v1/auth/login", content=oversized_chunks())
    assert chunked.status_code == 413
    assert chunked.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


async def test_untrusted_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/health/live",
        headers={"X-Request-ID": "unsafe request id with spaces"},
    )
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] != "unsafe request id with spaces"
