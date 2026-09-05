from __future__ import annotations

from datetime import datetime
from typing import Any, NoReturn

from app.core.config import Settings
from app.core.exceptions import AppError
from app.integrations.videos.base import (
    PlaybackGrant,
    ProviderUpload,
    VideoMetadata,
    VideoProvider,
)
from app.models.enums import UploadProtocol, VideoStatus


class DemoVideoProvider(VideoProvider):
    """Read-only provider for Drovixa-owned showcase clips bundled with the API."""

    name = "drovixa_demo"
    _clips = frozenset({"horizontal-01", "horizontal-02", "vertical-01", "vertical-02"})

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.DEMO_MEDIA_BASE_URL.rstrip("/")

    @staticmethod
    def _read_only() -> NoReturn:
        raise AppError(
            "DEMO_PROVIDER_READ_ONLY",
            "The showcase video provider is read-only.",
            status_code=409,
        )

    def _clip(self, playback_id: str | None) -> str:
        if playback_id not in self._clips:
            raise AppError(
                "VIDEO_NOT_READY",
                "The showcase clip is unavailable.",
                status_code=409,
            )
        return playback_id

    async def upload_video(
        self, *, source_url: str, name: str, require_signed_urls: bool = True
    ) -> VideoMetadata:
        del source_url, name, require_signed_urls
        self._read_only()

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
        del (
            file_name,
            content_type,
            file_size_bytes,
            max_duration_seconds,
            protocol,
            creator_id,
            external_id,
        )
        self._read_only()

    async def get_video_status(self, provider_asset_id: str) -> VideoMetadata:
        del provider_asset_id
        self._read_only()

    async def delete_video(self, provider_asset_id: str) -> None:
        del provider_asset_id
        self._read_only()

    def get_playback_url(self, playback_token: str) -> str:
        clip = self._clip(playback_token)
        return f"{self.base_url}/video/{clip}/index.m3u8"

    async def create_signed_url(
        self,
        *,
        provider_asset_id: str,
        playback_id: str | None,
        expires_at: datetime,
        country_code: str | None,
    ) -> PlaybackGrant:
        del provider_asset_id, country_code
        return PlaybackGrant(
            hls_url=self.get_playback_url(self._clip(playback_id)),
            dash_url=None,
            expires_at=expires_at,
        )

    def generate_thumbnail(self, provider_asset_id: str, *, time_seconds: int = 0) -> str:
        del provider_asset_id, time_seconds
        return f"{self.base_url}/branding/demo-thumbnail.jpg"

    async def get_video_metadata(self, provider_asset_id: str) -> VideoMetadata:
        return VideoMetadata(provider_asset_id=provider_asset_id, status=VideoStatus.READY)

    def verify_webhook(self, *, body: bytes, signature: str | None) -> datetime:
        del body, signature
        self._read_only()

    def parse_webhook(self, payload: dict[str, Any]) -> VideoMetadata:
        del payload
        self._read_only()
