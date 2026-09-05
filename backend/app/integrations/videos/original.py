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


class OriginalVideoProvider(VideoProvider):
    """Read-only playback for Drovixa-owned original productions bundled with the API."""

    name = "drovixa_original"
    _assets = frozenset({"minwi-nan-jakmel-ep01"})

    def __init__(self, settings: Settings) -> None:
        self.base_url = settings.ORIGINAL_MEDIA_BASE_URL.rstrip("/")

    @staticmethod
    def _read_only() -> NoReturn:
        raise AppError(
            "ORIGINAL_PROVIDER_READ_ONLY",
            "Drovixa Original assets are managed by the publishing pipeline.",
            status_code=409,
        )

    def _asset(self, playback_id: str | None) -> str:
        if playback_id not in self._assets:
            raise AppError(
                "VIDEO_NOT_READY",
                "This Drovixa Original is not ready for playback.",
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
        return await self.get_video_metadata(provider_asset_id)

    async def delete_video(self, provider_asset_id: str) -> None:
        del provider_asset_id
        self._read_only()

    def get_playback_url(self, playback_token: str) -> str:
        asset = self._asset(playback_token)
        return f"{self.base_url}/video/{asset}/index.m3u8"

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
            hls_url=self.get_playback_url(self._asset(playback_id)),
            dash_url=None,
            expires_at=expires_at,
        )

    def generate_thumbnail(self, provider_asset_id: str, *, time_seconds: int = 0) -> str:
        del provider_asset_id, time_seconds
        return f"{self.base_url}/thumbnails/minwi-nan-jakmel-ep01.jpg"

    async def get_video_metadata(self, provider_asset_id: str) -> VideoMetadata:
        del provider_asset_id
        return VideoMetadata(
            provider_asset_id="drovixa-original:minwi-nan-jakmel:episode-1:v1",
            status=VideoStatus.READY,
            duration_seconds=121,
            width=720,
            height=1280,
            thumbnail_url=f"{self.base_url}/thumbnails/minwi-nan-jakmel-ep01.jpg",
            playback_id="minwi-nan-jakmel-ep01",
        )

    def verify_webhook(self, *, body: bytes, signature: str | None) -> datetime:
        del body, signature
        self._read_only()

    def parse_webhook(self, payload: dict[str, Any]) -> VideoMetadata:
        del payload
        self._read_only()
