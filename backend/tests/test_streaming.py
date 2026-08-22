from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.videos import get_video_provider
from app.integrations.videos.base import (
    PlaybackGrant,
    ProviderUpload,
    VideoMetadata,
    VideoProvider,
)
from app.integrations.videos.cloudflare import CloudflareStreamProvider
from app.main import app
from app.models.base import utcnow
from app.models.configuration import FeatureFlag
from app.models.content import Content, Episode, Movie, Series, VideoAsset
from app.models.enums import (
    ContentStatus,
    ContentType,
    ContentVisibility,
    EpisodeAccessType,
    Orientation,
    SeriesStatus,
    UploadProtocol,
    VideoStatus,
)
from app.models.rbac import Role
from app.models.streaming import PlaybackSession, UserEntitlement, VideoWebhookEvent
from app.models.user import User
from app.schemas.streaming import UploadSessionCreate


class FakeVideoProvider(VideoProvider):
    name = "cloudflare_stream"

    async def upload_video(
        self, *, source_url: str, name: str, require_signed_urls: bool = True
    ) -> VideoMetadata:
        del source_url, name, require_signed_urls
        return VideoMetadata(uuid4().hex, VideoStatus.PROCESSING)

    async def get_upload_url(
        self,
        *,
        file_name: str,
        content_type: str,
        file_size_bytes: int,
        max_duration_seconds: int,
        protocol: UploadProtocol,
        creator_id: str,
        external_id: str,
    ) -> ProviderUpload:
        del file_name, content_type, file_size_bytes, max_duration_seconds, creator_id, external_id
        provider_id = uuid4().hex
        return ProviderUpload(
            provider_id,
            f"https://uploads.example.test/{provider_id}",
            protocol,
            headers={"Tus-Resumable": "1.0.0"} if protocol == UploadProtocol.TUS else {},
        )

    async def get_video_status(self, provider_asset_id: str) -> VideoMetadata:
        return VideoMetadata(
            provider_asset_id,
            VideoStatus.READY,
            duration_seconds=100,
            width=1080,
            height=1920,
            thumbnail_url="https://images.example.test/thumb.jpg",
            playback_id=provider_asset_id,
        )

    async def delete_video(self, provider_asset_id: str) -> None:
        del provider_asset_id

    def get_playback_url(self, playback_token: str) -> str:
        return f"https://video.example.test/{playback_token}/video.m3u8"

    async def create_signed_url(
        self,
        *,
        provider_asset_id: str,
        playback_id: str | None,
        expires_at: datetime,
        country_code: str | None,
    ) -> PlaybackGrant:
        del playback_id
        country = country_code or "global"
        return PlaybackGrant(
            hls_url=f"https://video.example.test/{provider_asset_id}/{country}/video.m3u8",
            dash_url=f"https://video.example.test/{provider_asset_id}/{country}/video.mpd",
            expires_at=expires_at,
        )

    def generate_thumbnail(self, provider_asset_id: str, *, time_seconds: int = 0) -> str:
        return f"https://images.example.test/{provider_asset_id}/{time_seconds}.jpg"

    async def get_video_metadata(self, provider_asset_id: str) -> VideoMetadata:
        return await self.get_video_status(provider_asset_id)

    def verify_webhook(self, *, body: bytes, signature: str | None) -> datetime:
        del body
        if signature != "valid":
            raise ValueError("invalid test signature")
        return utcnow()

    def parse_webhook(self, payload: dict[str, Any]) -> VideoMetadata:
        return VideoMetadata(
            provider_asset_id=str(payload["uid"]),
            status=VideoStatus.READY,
            duration_seconds=100,
            width=1080,
            height=1920,
            thumbnail_url="https://images.example.test/ready.jpg",
            playback_id=str(payload["uid"]),
            raw=payload,
        )


@pytest.fixture
def fake_provider() -> FakeVideoProvider:
    provider = FakeVideoProvider()
    app.dependency_overrides[get_video_provider] = lambda: provider
    return provider


@pytest.fixture(autouse=True)
def clear_provider_override() -> Any:
    yield
    app.dependency_overrides.pop(get_video_provider, None)


async def create_published_episode(
    db: AsyncSession,
    *,
    access_type: EpisodeAccessType = EpisodeAccessType.FREE,
    allowed_countries: list[str] | None = None,
) -> tuple[Content, Episode, VideoAsset]:
    asset = VideoAsset(
        provider="cloudflare_stream",
        provider_asset_id=uuid4().hex,
        status=VideoStatus.READY,
        duration_seconds=100,
        width=1080,
        height=1920,
        playback_id=uuid4().hex,
        ready_at=utcnow(),
        asset_metadata={},
    )
    content = Content(
        type=ContentType.SERIES,
        title="Phase Three Story",
        slug=f"phase-three-story-{uuid4().hex[:8]}",
        status=ContentStatus.PUBLISHED,
        visibility=ContentVisibility.PUBLIC,
        published_at=utcnow(),
        allowed_countries=allowed_countries or [],
        blocked_countries=[],
    )
    series = Series(
        content=content,
        series_status=SeriesStatus.ONGOING,
        orientation=Orientation.VERTICAL,
    )
    episode = Episode(
        series=series,
        episode_number=1,
        title="Episode 1",
        video_asset=asset,
        duration_seconds=100,
        access_type=access_type,
        orientation=Orientation.VERTICAL,
        status=ContentStatus.PUBLISHED,
        published_at=utcnow(),
    )
    db.add_all([asset, content, series, episode])
    await db.commit()
    return content, episode, asset


async def create_published_movie(
    db: AsyncSession,
    *,
    access_type: EpisodeAccessType = EpisodeAccessType.FREE,
) -> tuple[Content, Movie, VideoAsset]:
    asset = VideoAsset(
        provider="cloudflare_stream",
        provider_asset_id=uuid4().hex,
        status=VideoStatus.READY,
        duration_seconds=300,
        width=1920,
        height=1080,
        playback_id=uuid4().hex,
        ready_at=utcnow(),
        asset_metadata={},
    )
    content = Content(
        type=ContentType.MOVIE,
        title="Phase Three Movie",
        slug=f"phase-three-movie-{uuid4().hex[:8]}",
        status=ContentStatus.PUBLISHED,
        visibility=ContentVisibility.PUBLIC,
        published_at=utcnow(),
        allowed_countries=[],
        blocked_countries=[],
    )
    movie = Movie(
        content=content,
        video_asset=asset,
        duration_seconds=300,
        access_type=access_type,
    )
    db.add_all([asset, content, movie])
    await db.commit()
    return content, movie, asset


async def test_admin_direct_upload_and_idempotent_ready_webhook(
    client: AsyncClient,
    db: AsyncSession,
    admin_headers: dict[str, str],
    fake_provider: FakeVideoProvider,
) -> None:
    del fake_provider
    response = await client.post(
        "/api/v1/admin/video-assets/upload-sessions",
        headers=admin_headers,
        json={
            "file_name": "episode-001.mp4",
            "content_type": "video/mp4",
            "file_size_bytes": 250 * 1024 * 1024,
            "max_duration_seconds": 600,
            "protocol": "auto",
        },
    )
    assert response.status_code == 201, response.text
    upload = response.json()["data"]
    assert upload["protocol"] == "tus"
    assert upload["upload_headers"] == {"Tus-Resumable": "1.0.0"}
    asset = await db.get(VideoAsset, UUID(upload["video_asset_id"]))
    assert asset is not None and asset.status == VideoStatus.UPLOADING

    webhook = {
        "uid": asset.provider_asset_id,
        "readyToStream": True,
        "status": {"state": "ready", "pctComplete": "100"},
    }
    first = await client.post(
        "/api/v1/webhooks/videos/cloudflare_stream",
        headers={"Webhook-Signature": "valid"},
        json=webhook,
    )
    second = await client.post(
        "/api/v1/webhooks/videos/cloudflare_stream",
        headers={"Webhook-Signature": "valid"},
        json=webhook,
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["data"]["duplicate"] is True
    await db.refresh(asset)
    assert asset.status == VideoStatus.READY
    events = (await db.scalars(select(VideoWebhookEvent))).all()
    assert len(events) == 1


async def test_playback_progress_continue_history_and_view_deduplication(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    fake_provider: FakeVideoProvider,
) -> None:
    del fake_provider
    content, episode, _ = await create_published_episode(db)
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    authorization = await client.post(
        f"/api/v1/playback/{episode.id}/authorize",
        headers=headers,
        json={},
    )
    assert authorization.status_code == 200, authorization.text
    grant = authorization.json()["data"]
    assert grant["hls_url"].endswith("/global/video.m3u8")

    first = await client.post(
        "/api/v1/progress",
        headers=headers,
        json={
            "playback_session_id": grant["playback_session_id"],
            "position_seconds": 45,
            "duration_seconds": 100,
        },
    )
    assert first.status_code == 200, first.text
    progress_id = first.json()["data"]["id"]
    second = await client.post(
        "/api/v1/progress",
        headers=headers,
        json={
            "playback_session_id": grant["playback_session_id"],
            "position_seconds": 55,
            "duration_seconds": 100,
        },
    )
    assert second.status_code == 200
    await db.refresh(content)
    assert content.view_count == 1

    continuing = await client.get("/api/v1/continue-watching", headers=headers)
    history = await client.get("/api/v1/history", headers=headers)
    assert continuing.status_code == 200
    assert continuing.json()["meta"]["total"] == 1
    assert continuing.json()["data"][0]["progress"]["id"] == progress_id
    assert history.json()["meta"]["total"] == 1

    completed = await client.post(
        "/api/v1/progress",
        headers=headers,
        json={
            "playback_session_id": grant["playback_session_id"],
            "position_seconds": 95,
            "duration_seconds": 100,
        },
    )
    assert completed.json()["data"]["completed"] is True
    assert (await client.get("/api/v1/continue-watching", headers=headers)).json()["meta"][
        "total"
    ] == 0


async def test_guest_geo_and_entitlement_authorization(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    fake_provider: FakeVideoProvider,
) -> None:
    del fake_provider
    _, free_episode, _ = await create_published_episode(db, allowed_countries=["BR"])
    blocked = await client.post(
        f"/api/v1/playback/{free_episode.id}/authorize",
        json={"client_device_id": "guest-device-001"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "GEO_BLOCKED"
    allowed = await client.post(
        f"/api/v1/playback/{free_episode.id}/authorize",
        headers={"CF-IPCountry": "BR"},
        json={"client_device_id": "guest-device-001"},
    )
    assert allowed.status_code == 200, allowed.text
    assert "/BR/video.m3u8" in allowed.json()["data"]["hls_url"]

    locked_content, locked_episode, _ = await create_published_episode(
        db, access_type=EpisodeAccessType.COIN_UNLOCK
    )
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    locked = await client.post(
        f"/api/v1/playback/{locked_episode.id}/authorize", headers=headers, json={}
    )
    assert locked.status_code == 403
    assert locked.json()["error"]["code"] == "CONTENT_LOCKED"

    user_id = jwt.decode(
        str(registered["access_token"]),
        options={"verify_signature": False},
    )["sub"]
    db.add(
        UserEntitlement(
            user_id=UUID(user_id),
            content_type=ContentType.SERIES,
            content_id=locked_content.id,
            episode_id=locked_episode.id,
            source="admin_test_grant",
            is_permanent=True,
        )
    )
    await db.commit()
    unlocked = await client.post(
        f"/api/v1/playback/{locked_episode.id}/authorize", headers=headers, json={}
    )
    assert unlocked.status_code == 200, unlocked.text


async def test_cloudflare_signature_verification_and_local_signed_token() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    settings = Settings(
        _env_file=None,
        APP_ENV="testing",
        CLOUDFLARE_STREAM_WEBHOOK_SECRET="webhook-secret",
        CLOUDFLARE_STREAM_CUSTOMER_CODE="customer-code",
        CLOUDFLARE_STREAM_SIGNING_KEY_ID="key-id",
        CLOUDFLARE_STREAM_SIGNING_KEY_PEM_B64=base64.b64encode(private_pem).decode(),
    )
    provider = CloudflareStreamProvider(settings)
    body = b'{"uid":"asset-123"}'
    timestamp = int(datetime.now(UTC).timestamp())
    digest = hmac.new(
        b"webhook-secret",
        str(timestamp).encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    verified = provider.verify_webhook(
        body=body,
        signature=f"time={timestamp},sig1={digest}",
    )
    assert int(verified.timestamp()) == timestamp

    expires = datetime.now(UTC) + timedelta(minutes=10)
    grant = await provider.create_signed_url(
        provider_asset_id="asset-123",
        playback_id=None,
        expires_at=expires,
        country_code="BR",
    )
    token = grant.hls_url.split("/", maxsplit=3)[3].split("/", maxsplit=1)[0]
    public_key = private_key.public_key()
    claims = jwt.decode(token, public_key, algorithms=["RS256"])
    assert claims["sub"] == "asset-123"
    assert claims["accessRules"][0]["country"] == ["BR"]

    official_error_shape = provider.parse_webhook(
        {
            "uid": "asset-failed",
            "readyToStream": False,
            "status": {
                "state": "error",
                "errorReasonCode": "ERR_MALFORMED_VIDEO",
                "errorReasonText": "The video is malformed.",
            },
        }
    )
    assert official_error_shape.status == VideoStatus.FAILED
    assert official_error_shape.error_code == "ERR_MALFORMED_VIDEO"
    assert official_error_shape.error_message == "The video is malformed."


async def test_admin_ingest_refresh_and_safe_provider_delete(
    client: AsyncClient,
    db: AsyncSession,
    admin_headers: dict[str, str],
    fake_provider: FakeVideoProvider,
) -> None:
    del fake_provider
    ingested = await client.post(
        "/api/v1/admin/video-assets/ingest",
        headers=admin_headers,
        json={
            "source_url": "https://private-storage.example.test/episode.mp4",
            "file_name": "episode.mp4",
        },
    )
    assert ingested.status_code == 201, ingested.text
    asset_id = ingested.json()["data"]["id"]
    refreshed = await client.post(
        f"/api/v1/admin/video-assets/{asset_id}/refresh", headers=admin_headers
    )
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["data"]["status"] == "ready"
    deleted = await client.delete(
        f"/api/v1/admin/video-assets/{asset_id}/provider", headers=admin_headers
    )
    assert deleted.status_code == 200, deleted.text
    asset = await db.get(VideoAsset, UUID(asset_id))
    assert asset is not None and asset.status == VideoStatus.DELETED

    _, _, attached_asset = await create_published_episode(db)
    conflict = await client.delete(
        f"/api/v1/admin/video-assets/{attached_asset.id}/provider", headers=admin_headers
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "VIDEO_ASSET_IN_USE"


async def test_movie_playback_and_history_controls(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    fake_provider: FakeVideoProvider,
) -> None:
    del fake_provider
    _, movie, _ = await create_published_movie(db)
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    authorized = await client.post(
        f"/api/v1/playback/movies/{movie.id}/authorize", headers=headers, json={}
    )
    assert authorized.status_code == 200, authorized.text
    playback_id = authorized.json()["data"]["playback_session_id"]
    progress = await client.post(
        "/api/v1/progress",
        headers=headers,
        json={
            "playback_session_id": playback_id,
            "position_seconds": 120,
            "duration_seconds": 300,
        },
    )
    progress_id = progress.json()["data"]["id"]
    restarted = await client.post(
        f"/api/v1/continue-watching/{progress_id}/restart", headers=headers
    )
    assert restarted.status_code == 200
    removed = await client.delete(f"/api/v1/continue-watching/{progress_id}", headers=headers)
    assert removed.status_code == 200
    assert (await client.get("/api/v1/continue-watching", headers=headers)).json()["meta"][
        "total"
    ] == 0

    history = await client.get("/api/v1/history", headers=headers)
    history_id = history.json()["data"][0]["id"]
    deleted = await client.delete(f"/api/v1/history/{history_id}", headers=headers)
    assert deleted.status_code == 200
    cleared = await client.request(
        "DELETE",
        "/api/v1/history",
        headers=headers,
        json={"confirmation": "clear"},
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["deleted"] == 0


async def test_device_limit_and_unavailable_video_errors(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    register_payload: dict[str, object],
    fake_provider: FakeVideoProvider,
) -> None:
    del fake_provider
    _, episode, asset = await create_published_episode(db)
    second_login_payload = {
        "email": register_payload["email"],
        "password": register_payload["password"],
        "device": {
            "device_id": "second-device-87654321",
            "name": "Second Phone",
            "platform": "ios",
        },
    }
    second_login = await client.post("/api/v1/auth/login", json=second_login_payload)
    assert second_login.status_code == 200
    second_headers = {"Authorization": f"Bearer {second_login.json()['data']['access_token']}"}
    assert (
        await client.post(
            f"/api/v1/playback/{episode.id}/authorize", headers=second_headers, json={}
        )
    ).status_code == 200
    first_headers = {"Authorization": f"Bearer {registered['access_token']}"}
    limited = await client.post(
        f"/api/v1/playback/{episode.id}/authorize", headers=first_headers, json={}
    )
    assert limited.status_code == 403
    assert limited.json()["error"]["code"] == "DEVICE_LIMIT_REACHED"

    asset.status = VideoStatus.PROCESSING
    await db.commit()
    guest = await client.post(
        f"/api/v1/playback/{episode.id}/authorize",
        json={"client_device_id": "guest-device-002"},
    )
    assert guest.status_code == 409
    assert guest.json()["error"]["code"] == "VIDEO_NOT_READY"


async def test_cloudflare_http_adapter_and_failure_paths() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/stream/direct_upload"):
            return httpx.Response(
                200,
                json={
                    "result": {
                        "uid": "basic-asset",
                        "uploadURL": "https://upload.example.test/basic",
                    }
                },
            )
        if path.endswith("/stream") and request.url.params.get("direct_user") == "true":
            return httpx.Response(
                201,
                headers={
                    "Location": "https://upload.example.test/tus/tus-asset",
                    "stream-media-id": "tus-asset",
                },
            )
        if path.endswith("/stream/copy"):
            return httpx.Response(
                200,
                json={
                    "result": {
                        "uid": "copy-asset",
                        "readyToStream": False,
                        "status": {"state": "downloading"},
                    }
                },
            )
        if request.method == "DELETE":
            return httpx.Response(200, json={"result": "deleted"})
        return httpx.Response(
            200,
            json={
                "result": {
                    "uid": "basic-asset",
                    "duration": 101.4,
                    "readyToStream": True,
                    "status": {"state": "ready"},
                    "input": {"width": 1920, "height": 1080},
                    "thumbnail": "https://images.example.test/basic.jpg",
                }
            },
        )

    settings = Settings(
        _env_file=None,
        APP_ENV="testing",
        CLOUDFLARE_ACCOUNT_ID="account-id",
        CLOUDFLARE_STREAM_API_TOKEN="api-token",
        CLOUDFLARE_STREAM_CUSTOMER_CODE="customer-code",
    )
    provider = CloudflareStreamProvider(settings, transport=httpx.MockTransport(handler))
    basic = await provider.get_upload_url(
        file_name="episode.mp4",
        content_type="video/mp4",
        file_size_bytes=100,
        max_duration_seconds=600,
        protocol=UploadProtocol.BASIC,
        creator_id="creator",
        external_id="local-asset",
    )
    tus = await provider.get_upload_url(
        file_name="episode.mp4",
        content_type="video/mp4",
        file_size_bytes=300 * 1024 * 1024,
        max_duration_seconds=600,
        protocol=UploadProtocol.TUS,
        creator_id="creator",
        external_id="local-asset",
    )
    copied = await provider.upload_video(
        source_url="https://storage.example.test/video.mp4", name="video.mp4"
    )
    metadata = await provider.get_video_status("basic-asset")
    await provider.delete_video("basic-asset")
    assert basic.provider_asset_id == "basic-asset"
    assert tus.provider_asset_id == "tus-asset"
    assert copied.status == VideoStatus.PROCESSING
    assert metadata.status == VideoStatus.READY
    assert metadata.duration_seconds == 101
    assert provider.get_playback_url("token").endswith("/token/manifest/video.m3u8")
    assert "time=12s" in provider.generate_thumbnail("basic-asset", time_seconds=12)

    failing = CloudflareStreamProvider(
        settings,
        transport=httpx.MockTransport(lambda _: httpx.Response(500)),
    )
    with pytest.raises(AppError, match="video provider"):
        await failing.get_video_status("asset")


async def test_cloudflare_validation_failures() -> None:
    unconfigured = CloudflareStreamProvider(Settings(_env_file=None, APP_ENV="testing"))
    with pytest.raises(AppError) as credentials:
        unconfigured._api_credentials()
    assert credentials.value.code == "VIDEO_PROVIDER_NOT_CONFIGURED"
    with pytest.raises(AppError):
        unconfigured.get_playback_url("token")
    with pytest.raises(AppError) as missing_signature:
        unconfigured.verify_webhook(body=b"{}", signature=None)
    assert missing_signature.value.code == "VIDEO_WEBHOOK_NOT_CONFIGURED"

    provider = CloudflareStreamProvider(
        Settings(
            _env_file=None,
            APP_ENV="testing",
            CLOUDFLARE_STREAM_WEBHOOK_SECRET="secret",
            CLOUDFLARE_STREAM_CUSTOMER_CODE="code",
            CLOUDFLARE_STREAM_SIGNING_KEY_ID="key",
            CLOUDFLARE_STREAM_SIGNING_KEY_PEM_B64="not-base64",
        )
    )
    with pytest.raises(AppError) as stale:
        provider.verify_webhook(body=b"{}", signature="time=1,sig1=bad")
    assert stale.value.code == "INVALID_WEBHOOK_SIGNATURE"
    now = int(datetime.now(UTC).timestamp())
    with pytest.raises(AppError) as invalid:
        provider.verify_webhook(body=b"{}", signature=f"time={now},sig1=bad")
    assert invalid.value.code == "INVALID_WEBHOOK_SIGNATURE"
    with pytest.raises(AppError) as signing:
        await provider.create_signed_url(
            provider_asset_id="asset",
            playback_id=None,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            country_code=None,
        )
    assert signing.value.code == "VIDEO_SIGNING_NOT_CONFIGURED"
    with pytest.raises(AppError):
        provider.parse_webhook({})


async def test_access_policy_and_scheduled_free_branches(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    fake_provider: FakeVideoProvider,
) -> None:
    del fake_provider
    headers = {"Authorization": f"Bearer {registered['access_token']}"}

    _, premium_episode, _ = await create_published_episode(
        db, access_type=EpisodeAccessType.PREMIUM_SUBSCRIPTION
    )
    denied = await client.post(
        f"/api/v1/playback/{premium_episode.id}/authorize", headers=headers, json={}
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PREMIUM_REQUIRED"

    _, mixed_episode, _ = await create_published_episode(
        db, access_type=EpisodeAccessType.PREMIUM_OR_COIN
    )
    mixed = await client.post(
        f"/api/v1/playback/{mixed_episode.id}/authorize", headers=headers, json={}
    )
    assert mixed.status_code == 403
    assert mixed.json()["error"]["code"] == "PREMIUM_REQUIRED"

    _, ad_episode, _ = await create_published_episode(db, access_type=EpisodeAccessType.AD_UNLOCK)
    ad_locked = await client.post(
        f"/api/v1/playback/{ad_episode.id}/authorize", headers=headers, json={}
    )
    assert ad_locked.status_code == 403
    assert ad_locked.json()["error"]["code"] == "CONTENT_LOCKED"

    _, scheduled_episode, _ = await create_published_episode(
        db, access_type=EpisodeAccessType.SCHEDULED_FREE
    )
    scheduled_episode.free_from = utcnow() + timedelta(days=1)
    await db.commit()
    scheduled = await client.post(
        f"/api/v1/playback/{scheduled_episode.id}/authorize", headers=headers, json={}
    )
    assert scheduled.status_code == 403
    assert scheduled.json()["error"]["code"] == "CONTENT_NOT_AVAILABLE"
    guest_locked = await client.post(
        f"/api/v1/playback/{scheduled_episode.id}/authorize",
        json={"client_device_id": "guest-scheduled-001"},
    )
    assert guest_locked.status_code == 401

    scheduled_episode.free_from = utcnow() - timedelta(minutes=1)
    scheduled_episode.free_until = utcnow() + timedelta(minutes=5)
    await db.commit()
    guest_free = await client.post(
        f"/api/v1/playback/{scheduled_episode.id}/authorize",
        json={"client_device_id": "guest-scheduled-001"},
    )
    assert guest_free.status_code == 200, guest_free.text

    user = await db.scalar(select(User).where(User.email == "viewer@example.com"))
    premium_role = await db.scalar(select(Role).where(Role.name == "premium_user"))
    assert user is not None and premium_role is not None
    user.roles.append(premium_role)
    await db.commit()
    premium = await client.post(
        f"/api/v1/playback/{premium_episode.id}/authorize", headers=headers, json={}
    )
    assert premium.status_code == 200, premium.text

    guest_flag = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == "guest_mode_enabled"))
    assert guest_flag is not None
    guest_flag.enabled = False
    _, free_episode, _ = await create_published_episode(db)
    disabled = await client.post(
        f"/api/v1/playback/{free_episode.id}/authorize",
        json={"client_device_id": "guest-disabled-001"},
    )
    assert disabled.status_code == 401


async def test_playback_availability_and_target_errors(
    client: AsyncClient,
    db: AsyncSession,
    fake_provider: FakeVideoProvider,
) -> None:
    del fake_provider
    missing_episode = await client.post(
        f"/api/v1/playback/{uuid4()}/authorize",
        json={"client_device_id": "guest-errors-001"},
    )
    assert missing_episode.status_code == 404
    missing_movie = await client.post(
        f"/api/v1/playback/movies/{uuid4()}/authorize",
        json={"client_device_id": "guest-errors-001"},
    )
    assert missing_movie.status_code == 404

    content, episode, asset = await create_published_episode(db)

    async def authorize(country: str | None = None) -> httpx.Response:
        request_headers = {"CF-IPCountry": country} if country else {}
        return await client.post(
            f"/api/v1/playback/{episode.id}/authorize",
            headers=request_headers,
            json={"client_device_id": "guest-errors-001"},
        )

    content.visibility = ContentVisibility.PRIVATE
    await db.commit()
    assert (await authorize()).status_code == 403
    content.visibility = ContentVisibility.PUBLIC
    content.published_at = utcnow() + timedelta(days=1)
    await db.commit()
    assert (await authorize()).status_code == 403
    content.published_at = utcnow()
    content.license_start = utcnow() + timedelta(days=1)
    await db.commit()
    assert (await authorize()).status_code == 403
    content.license_start = None
    content.license_end = utcnow() - timedelta(seconds=1)
    await db.commit()
    assert (await authorize()).status_code == 403
    content.license_end = None
    content.blocked_countries = ["BR"]
    await db.commit()
    geo = await authorize("BR")
    assert geo.status_code == 403
    assert geo.json()["error"]["code"] == "GEO_BLOCKED"
    content.blocked_countries = []
    episode.published_at = utcnow() + timedelta(days=1)
    await db.commit()
    assert (await authorize()).status_code == 403
    episode.published_at = utcnow()
    episode.video_asset = None
    await db.commit()
    unavailable = await authorize()
    assert unavailable.status_code == 409
    episode.video_asset = asset
    asset.provider = "mux"
    await db.commit()
    mismatch = await authorize()
    assert mismatch.status_code == 503
    asset.provider = "cloudflare_stream"
    await db.commit()
    missing_device = await client.post(f"/api/v1/playback/{episode.id}/authorize", json={})
    assert missing_device.status_code == 422

    _, movie, _ = await create_published_movie(db)
    movie.video_asset = None
    await db.commit()
    movie_unavailable = await client.post(
        f"/api/v1/playback/movies/{movie.id}/authorize",
        json={"client_device_id": "guest-errors-001"},
    )
    assert movie_unavailable.status_code == 409


async def test_progress_expiry_missing_controls_and_history_clear(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    fake_provider: FakeVideoProvider,
) -> None:
    del fake_provider
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    invalid = await client.post(
        "/api/v1/progress",
        headers=headers,
        json={
            "playback_session_id": str(uuid4()),
            "position_seconds": 1,
            "duration_seconds": 100,
        },
    )
    assert invalid.status_code == 403
    assert invalid.json()["error"]["code"] == "PLAYBACK_SESSION_INVALID"

    _, episode, _ = await create_published_episode(db)
    authorized = await client.post(
        f"/api/v1/playback/{episode.id}/authorize", headers=headers, json={}
    )
    playback_id = UUID(authorized.json()["data"]["playback_session_id"])
    playback = await db.get(PlaybackSession, playback_id)
    assert playback is not None
    playback.expires_at = utcnow() - timedelta(seconds=1)
    await db.commit()
    expired = await client.post(
        "/api/v1/progress",
        headers=headers,
        json={
            "playback_session_id": str(playback_id),
            "position_seconds": 1,
            "duration_seconds": 100,
        },
    )
    assert expired.status_code == 401
    assert expired.json()["error"]["code"] == "PLAYBACK_SESSION_EXPIRED"

    random_id = uuid4()
    assert (
        await client.delete(f"/api/v1/continue-watching/{random_id}", headers=headers)
    ).status_code == 404
    assert (
        await client.post(f"/api/v1/continue-watching/{random_id}/restart", headers=headers)
    ).status_code == 404
    assert (await client.delete(f"/api/v1/history/{random_id}", headers=headers)).status_code == 404

    playback.expires_at = utcnow() + timedelta(minutes=5)
    await db.commit()
    progress = await client.post(
        "/api/v1/progress",
        headers=headers,
        json={
            "playback_session_id": str(playback_id),
            "position_seconds": 10,
            "duration_seconds": 100,
        },
    )
    assert progress.status_code == 200
    cleared = await client.request(
        "DELETE", "/api/v1/history", headers=headers, json={"confirmation": "clear"}
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["deleted"] == 1


async def test_webhook_and_admin_streaming_error_paths(
    client: AsyncClient,
    db: AsyncSession,
    admin_headers: dict[str, str],
    fake_provider: FakeVideoProvider,
) -> None:
    del fake_provider
    unknown = await client.post(
        "/api/v1/webhooks/videos/cloudflare_stream",
        headers={"Webhook-Signature": "valid"},
        json={"uid": uuid4().hex, "status": {"state": "ready"}, "readyToStream": True},
    )
    assert unknown.status_code == 200
    assert unknown.json()["data"]["status"] == "ignored"
    wrong_provider = await client.post(
        "/api/v1/webhooks/videos/mux",
        headers={"Webhook-Signature": "valid"},
        json={"uid": uuid4().hex},
    )
    assert wrong_provider.status_code == 404
    invalid_json = await client.post(
        "/api/v1/webhooks/videos/cloudflare_stream",
        headers={"Webhook-Signature": "valid", "Content-Type": "application/json"},
        content=b"not-json",
    )
    assert invalid_json.status_code == 400
    invalid_list = await client.post(
        "/api/v1/webhooks/videos/cloudflare_stream",
        headers={"Webhook-Signature": "valid"},
        json=["not", "an", "object"],
    )
    assert invalid_list.status_code == 400

    for payload in (
        {
            "file_name": "episode.txt",
            "content_type": "video/mp4",
            "file_size_bytes": 100,
            "max_duration_seconds": 60,
        },
        {
            "file_name": "episode.mp4",
            "content_type": "image/jpeg",
            "file_size_bytes": 100,
            "max_duration_seconds": 60,
        },
        {
            "file_name": "episode.mp4",
            "content_type": "video/mp4",
            "file_size_bytes": 201 * 1024 * 1024,
            "max_duration_seconds": 60,
            "protocol": "basic",
        },
    ):
        response = await client.post(
            "/api/v1/admin/video-assets/upload-sessions",
            headers=admin_headers,
            json=payload,
        )
        assert response.status_code == 422

    basic = await client.post(
        "/api/v1/admin/video-assets/upload-sessions",
        headers=admin_headers,
        json={
            "file_name": "episode.mp4",
            "content_type": "video/mp4",
            "file_size_bytes": 100,
            "max_duration_seconds": 60,
            "protocol": "basic",
        },
    )
    assert basic.status_code == 201
    asset = await db.get(VideoAsset, UUID(basic.json()["data"]["video_asset_id"]))
    assert asset is not None
    asset.provider = "mux"
    await db.commit()
    refresh = await client.post(
        f"/api/v1/admin/video-assets/{asset.id}/refresh", headers=admin_headers
    )
    assert refresh.status_code == 503
    deleted = await client.delete(
        f"/api/v1/admin/video-assets/{asset.id}/provider", headers=admin_headers
    )
    assert deleted.status_code == 503
    missing = await client.post(
        f"/api/v1/admin/video-assets/{uuid4()}/refresh", headers=admin_headers
    )
    assert missing.status_code == 404


async def test_cloudflare_malformed_provider_responses() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="testing",
        CLOUDFLARE_ACCOUNT_ID="account-id",
        CLOUDFLARE_STREAM_API_TOKEN="api-token",
        CLOUDFLARE_STREAM_CUSTOMER_CODE="customer-code",
    )

    invalid_json = CloudflareStreamProvider(
        settings,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"not-json")),
    )
    with pytest.raises(AppError):
        await invalid_json.get_video_status("asset")

    missing_result = CloudflareStreamProvider(
        settings,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"result": None})),
    )
    with pytest.raises(AppError):
        await missing_result.get_video_status("asset")

    missing_upload = CloudflareStreamProvider(
        settings,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"result": {}})),
    )
    with pytest.raises(AppError):
        await missing_upload.get_upload_url(
            file_name="video.mp4",
            content_type="video/mp4",
            file_size_bytes=100,
            max_duration_seconds=60,
            protocol=UploadProtocol.BASIC,
            creator_id="creator",
            external_id="local-asset",
        )

    missing_tus = CloudflareStreamProvider(
        settings,
        transport=httpx.MockTransport(lambda _: httpx.Response(201)),
    )
    with pytest.raises(AppError):
        await missing_tus.get_upload_url(
            file_name="video.mp4",
            content_type="video/mp4",
            file_size_bytes=300 * 1024 * 1024,
            max_duration_seconds=60,
            protocol=UploadProtocol.TUS,
            creator_id="creator",
            external_id="local-asset",
        )

    failed = CloudflareStreamProvider._metadata(
        {
            "uid": "failed-asset",
            "status": {
                "state": "error",
                "errReasonCode": "ERR_TEST",
                "errReasonText": "Processing failed",
            },
            "input": "unexpected",
        }
    )
    assert failed.status == VideoStatus.FAILED
    assert failed.error_code == "ERR_TEST"

    tus_location_only = CloudflareStreamProvider(
        settings,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                201, headers={"Location": "https://upload.example.test/tus/location-asset"}
            )
        ),
    )
    fallback = await tus_location_only.get_upload_url(
        file_name="video.mp4",
        content_type="video/mp4",
        file_size_bytes=300 * 1024 * 1024,
        max_duration_seconds=60,
        protocol=UploadProtocol.TUS,
        creator_id="creator",
        external_id="local-asset",
    )
    assert fallback.provider_asset_id == "location-asset"

    invalid_pem = CloudflareStreamProvider(
        Settings(
            _env_file=None,
            APP_ENV="testing",
            CLOUDFLARE_STREAM_CUSTOMER_CODE="customer-code",
            CLOUDFLARE_STREAM_SIGNING_KEY_ID="key-id",
            CLOUDFLARE_STREAM_SIGNING_KEY_PEM_B64=base64.b64encode(b"not-a-private-key").decode(),
        )
    )
    with pytest.raises(AppError):
        await invalid_pem.create_signed_url(
            provider_asset_id="asset",
            playback_id=None,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            country_code=None,
        )

    signed_provider = CloudflareStreamProvider(
        Settings(
            _env_file=None,
            APP_ENV="testing",
            CLOUDFLARE_STREAM_WEBHOOK_SECRET="secret",
        )
    )
    with pytest.raises(AppError):
        signed_provider.verify_webhook(body=b"{}", signature="time=not-an-int,sig1=value")
    unknown = CloudflareStreamProvider._metadata({"uid": "unknown-state", "status": {}})
    assert unknown.status == VideoStatus.PROCESSING


def test_upload_limits_reject_oversized_or_overlong_videos() -> None:
    with pytest.raises(ValueError, match="file exceeds"):
        UploadSessionCreate(
            file_name="too-large.mp4",
            content_type="video/mp4",
            file_size_bytes=10 * 1024 * 1024 * 1024 + 1,
            max_duration_seconds=60,
        )
    with pytest.raises(ValueError, match="duration exceeds"):
        UploadSessionCreate(
            file_name="too-long.mp4",
            content_type="video/mp4",
            file_size_bytes=100,
            max_duration_seconds=14401,
        )
