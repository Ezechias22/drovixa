from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.videos import get_video_provider
from app.integrations.videos.mux import MuxVideoProvider
from app.main import app
from app.models.content import VideoAsset
from app.models.enums import UploadProtocol, VideoStatus
from app.services.videos import apply_video_metadata


def mux_signing_key() -> tuple[bytes, Any]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return private_pem, private_key.public_key()


def mux_settings(private_pem: bytes | None = None) -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="testing",
        VIDEO_PROVIDER="mux",
        MUX_TOKEN_ID="mux-token-id",
        MUX_TOKEN_SECRET="mux-token-secret",
        MUX_SIGNING_KEY_ID="mux-signing-key",
        MUX_SIGNING_PRIVATE_KEY_B64=(
            base64.b64encode(private_pem).decode() if private_pem else None
        ),
        MUX_WEBHOOK_SECRET="mux-webhook-secret",
        MUX_UPLOAD_CORS_ORIGIN="http://localhost:3001",
    )


@pytest.fixture(autouse=True)
def clear_mux_provider_override() -> Any:
    yield
    app.dependency_overrides.pop(get_video_provider, None)


async def test_mux_adapter_direct_upload_poll_and_signed_playback() -> None:
    private_pem, public_key = mux_signing_key()
    captured_upload: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        authorization = request.headers.get("Authorization", "")
        assert authorization.startswith("Basic ")
        if request.method == "POST" and request.url.path.endswith("/uploads"):
            captured_upload.update(json.loads(request.content))
            return httpx.Response(
                201,
                json={
                    "data": {
                        "id": "mux-upload-123",
                        "url": "https://storage.example.test/mux-upload-123",
                        "status": "waiting",
                    }
                },
            )
        if request.method == "GET" and request.url.path.endswith("/uploads/mux-upload-123"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "mux-upload-123",
                        "status": "asset_created",
                        "asset_id": "mux-asset-123",
                    }
                },
            )
        if request.method == "GET" and request.url.path.endswith("/assets/mux-asset-123"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "id": "mux-asset-123",
                        "status": "ready",
                        "duration": 91.6,
                        "passthrough": "11111111-1111-1111-1111-111111111111",
                        "playback_ids": [{"id": "mux-playback-123", "policy": "signed"}],
                        "tracks": [{"type": "video", "max_width": 1080, "max_height": 1920}],
                    }
                },
            )
        return httpx.Response(404)

    provider = MuxVideoProvider(
        mux_settings(private_pem),
        transport=httpx.MockTransport(handler),
    )
    assert (
        provider.select_upload_protocol(requested="auto", file_size_bytes=10)
        == UploadProtocol.RESUMABLE
    )
    upload = await provider.get_upload_url(
        file_name="episode-01.mp4",
        content_type="video/mp4",
        file_size_bytes=100,
        max_duration_seconds=600,
        protocol=UploadProtocol.RESUMABLE,
        creator_id="admin-123",
        external_id="11111111-1111-1111-1111-111111111111",
    )
    assert upload.provider_asset_id == "mux-upload:mux-upload-123"
    assert upload.protocol == UploadProtocol.RESUMABLE
    assert upload.headers == {"Content-Type": "video/mp4"}
    assert captured_upload["new_asset_settings"]["playback_policies"] == ["signed"]
    assert captured_upload["new_asset_settings"]["video_quality"] == "basic"
    assert (
        captured_upload["new_asset_settings"]["passthrough"]
        == "11111111-1111-1111-1111-111111111111"
    )

    metadata = await provider.get_video_status(upload.provider_asset_id)
    assert metadata.provider_asset_id == "mux-asset-123"
    assert metadata.status == VideoStatus.READY
    assert metadata.playback_id == "mux-playback-123"
    assert metadata.duration_seconds == 92
    assert (metadata.width, metadata.height) == (1080, 1920)

    expires_at = datetime.now(UTC) + timedelta(minutes=15)
    grant = await provider.create_signed_url(
        provider_asset_id=metadata.provider_asset_id,
        playback_id=metadata.playback_id,
        expires_at=expires_at,
        country_code="HT",
    )
    assert grant.dash_url is None
    parsed = urlparse(grant.hls_url)
    assert parsed.path == "/mux-playback-123.m3u8"
    token = parse_qs(parsed.query)["token"][0]
    claims = jwt.decode(token, public_key, algorithms=["RS256"], audience="v")
    assert claims["sub"] == "mux-playback-123"
    assert claims["kid"] == "mux-signing-key"

    thumbnail = provider.generate_thumbnail("mux-playback-123", time_seconds=12)
    thumbnail_token = parse_qs(urlparse(thumbnail).query)["token"][0]
    thumbnail_claims = jwt.decode(
        thumbnail_token,
        public_key,
        algorithms=["RS256"],
        audience="t",
    )
    assert thumbnail_claims["params"] == {"time": 12}


async def test_mux_webhook_correlates_upload_to_local_asset(
    client: AsyncClient,
    db: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/uploads"):
            body = json.loads(request.content)
            external_id = body["new_asset_settings"]["passthrough"]
            return httpx.Response(
                201,
                json={
                    "data": {
                        "id": "mux-upload-webhook",
                        "url": "https://storage.example.test/mux-upload-webhook",
                        "status": "waiting",
                        "new_asset_settings": {"passthrough": external_id},
                    }
                },
            )
        return httpx.Response(404)

    provider = MuxVideoProvider(
        mux_settings(),
        transport=httpx.MockTransport(handler),
    )
    app.dependency_overrides[get_video_provider] = lambda: provider
    created = await client.post(
        "/api/v1/admin/video-assets/upload-sessions",
        headers=admin_headers,
        json={
            "file_name": "episode-02.mp4",
            "content_type": "video/mp4",
            "file_size_bytes": 500_000_000,
            "max_duration_seconds": 900,
            "protocol": "auto",
        },
    )
    assert created.status_code == 201, created.text
    session_data = created.json()["data"]
    assert session_data["provider"] == "mux"
    assert session_data["protocol"] == "resumable"
    local_asset_id = UUID(session_data["video_asset_id"])
    asset = await db.get(VideoAsset, local_asset_id)
    assert asset is not None
    assert asset.provider_asset_id == "mux-upload:mux-upload-webhook"

    event = {
        "id": "event-ready-123",
        "type": "video.asset.ready",
        "object": {"type": "asset", "id": "mux-asset-webhook"},
        "data": {
            "id": "mux-asset-webhook",
            "status": "ready",
            "duration": 120.2,
            "passthrough": str(local_asset_id),
            "playback_ids": [{"id": "mux-playback-webhook", "policy": "signed"}],
            "tracks": [{"type": "video", "max_width": 1920, "max_height": 1080}],
        },
    }
    raw_body = json.dumps(event, separators=(",", ":")).encode()
    timestamp = int(datetime.now(UTC).timestamp())
    signature = hmac.new(
        b"mux-webhook-secret",
        str(timestamp).encode() + b"." + raw_body,
        hashlib.sha256,
    ).hexdigest()
    ready = await client.post(
        "/api/v1/webhooks/videos/mux",
        headers={
            "Content-Type": "application/json",
            "Mux-Signature": f"t={timestamp},v1={signature}",
        },
        content=raw_body,
    )
    assert ready.status_code == 200, ready.text
    await db.refresh(asset)
    assert asset.provider_asset_id == "mux-asset-webhook"
    assert asset.playback_id == "mux-playback-webhook"
    assert asset.status == VideoStatus.READY
    assert asset.duration_seconds == 120


async def test_mux_rejects_bad_configuration_protocol_and_webhook() -> None:
    with pytest.raises(ValidationError, match="Mux configuration is incomplete"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            VIDEO_PROVIDER="mux",
            JWT_SECRET="a" * 40,
            REFRESH_SECRET="b" * 40,
            BACKEND_CORS_ORIGINS=["https://app.drovixa.example"],
            TRUSTED_HOSTS=["api.drovixa.example"],
            FORCE_HTTPS=True,
            METRICS_TOKEN="m" * 32,
        )
    with pytest.raises(ValidationError, match="MUX_UPLOAD_CORS_ORIGIN"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            VIDEO_PROVIDER="mux",
            JWT_SECRET="a" * 40,
            REFRESH_SECRET="b" * 40,
            BACKEND_CORS_ORIGINS=["https://app.drovixa.example"],
            TRUSTED_HOSTS=["api.drovixa.example"],
            FORCE_HTTPS=True,
            METRICS_TOKEN="m" * 32,
            MUX_TOKEN_ID="token-id",
            MUX_TOKEN_SECRET="token-secret",
            MUX_SIGNING_KEY_ID="signing-key-id",
            MUX_SIGNING_PRIVATE_KEY_B64="private-key",
            MUX_WEBHOOK_SECRET="webhook-secret",
            MUX_UPLOAD_CORS_ORIGIN="*",
        )
    unconfigured = MuxVideoProvider(Settings(_env_file=None, APP_ENV="testing"))
    with pytest.raises(AppError) as credentials:
        unconfigured._api_credentials()
    assert credentials.value.code == "VIDEO_PROVIDER_NOT_CONFIGURED"
    with pytest.raises(AppError) as protocol:
        unconfigured.select_upload_protocol(requested="tus", file_size_bytes=1)
    assert protocol.value.code == "VIDEO_UPLOAD_PROTOCOL_UNSUPPORTED"
    with pytest.raises(AppError) as webhook:
        unconfigured.verify_webhook(body=b"{}", signature=None)
    assert webhook.value.code == "VIDEO_WEBHOOK_NOT_CONFIGURED"

    provider = MuxVideoProvider(mux_settings())
    now = int(datetime.now(UTC).timestamp())
    with pytest.raises(AppError) as invalid:
        provider.verify_webhook(body=b"{}", signature=f"t={now},v1=bad")
    assert invalid.value.code == "INVALID_WEBHOOK_SIGNATURE"
    with pytest.raises(AppError) as stale:
        provider.verify_webhook(body=b"{}", signature="t=1,v1=bad")
    assert stale.value.code == "INVALID_WEBHOOK_SIGNATURE"
    ignored = provider.parse_webhook(
        {
            "type": "video.asset.track.ready",
            "object": {"type": "asset", "id": "asset-1"},
            "data": {"id": "track-1"},
        }
    )
    assert ignored.actionable is False


def test_ready_asset_does_not_regress_on_out_of_order_mux_event() -> None:
    asset = VideoAsset(
        provider="mux",
        provider_asset_id="mux-asset-terminal",
        status=VideoStatus.READY,
        playback_id="mux-playback-terminal",
        asset_metadata={"source": "direct_upload"},
    )
    provider = MuxVideoProvider(mux_settings())
    delayed = provider.parse_webhook(
        {
            "id": "delayed-created-event",
            "type": "video.asset.created",
            "object": {"type": "asset", "id": "mux-asset-terminal"},
            "data": {
                "id": "mux-asset-terminal",
                "status": "preparing",
                "passthrough": "11111111-1111-1111-1111-111111111111",
            },
        }
    )
    apply_video_metadata(asset, delayed)
    assert asset.status == VideoStatus.READY
    assert asset.playback_id == "mux-playback-terminal"
    assert asset.asset_metadata["source"] == "direct_upload"
