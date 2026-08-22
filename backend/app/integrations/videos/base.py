from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.enums import UploadProtocol, VideoStatus


@dataclass(frozen=True, slots=True)
class ProviderUpload:
    provider_asset_id: str
    upload_url: str
    protocol: UploadProtocol
    expires_at: datetime | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    provider_asset_id: str
    status: VideoStatus
    duration_seconds: int | None = None
    width: int | None = None
    height: int | None = None
    thumbnail_url: str | None = None
    playback_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    correlation_id: str | None = None
    actionable: bool = True
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PlaybackGrant:
    hls_url: str
    dash_url: str | None
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class DownloadGrant:
    url: str
    expires_at: datetime
    quality: str


class VideoProvider(ABC):
    name: str
    webhook_signature_header = "Webhook-Signature"

    def select_upload_protocol(self, *, requested: str, file_size_bytes: int) -> UploadProtocol:
        """Resolve a client upload preference to a provider-supported protocol."""
        if requested == "auto":
            return (
                UploadProtocol.TUS if file_size_bytes > 200 * 1024 * 1024 else UploadProtocol.BASIC
            )
        return UploadProtocol(requested)

    @abstractmethod
    async def upload_video(
        self, *, source_url: str, name: str, require_signed_urls: bool = True
    ) -> VideoMetadata:
        """Ask the provider to ingest a video from a private source URL."""

    @abstractmethod
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
        """Create a one-time direct upload session without exposing provider credentials."""

    @abstractmethod
    async def get_video_status(self, provider_asset_id: str) -> VideoMetadata:
        """Return current processing state and normalized metadata."""

    @abstractmethod
    async def delete_video(self, provider_asset_id: str) -> None:
        """Delete the provider copy."""

    @abstractmethod
    def get_playback_url(self, playback_token: str) -> str:
        """Build an HLS playback URL from a signed provider token."""

    @abstractmethod
    async def create_signed_url(
        self,
        *,
        provider_asset_id: str,
        playback_id: str | None,
        expires_at: datetime,
        country_code: str | None,
    ) -> PlaybackGrant:
        """Create short-lived HLS/DASH playback URLs."""

    async def create_signed_download_url(
        self,
        *,
        provider_asset_id: str,
        playback_id: str | None,
        expires_at: datetime,
        quality: str,
    ) -> DownloadGrant:
        """Return a short-lived progressive download URL when supported."""
        del provider_asset_id, playback_id, expires_at, quality
        from app.core.exceptions import AppError

        raise AppError(
            "DOWNLOAD_PROVIDER_UNSUPPORTED",
            "Secure downloads are unavailable for this video provider.",
            status_code=501,
        )

    @abstractmethod
    def generate_thumbnail(self, provider_asset_id: str, *, time_seconds: int = 0) -> str:
        """Build a provider thumbnail URL."""

    @abstractmethod
    async def get_video_metadata(self, provider_asset_id: str) -> VideoMetadata:
        """Return provider video metadata."""

    @abstractmethod
    def verify_webhook(self, *, body: bytes, signature: str | None) -> datetime:
        """Verify authenticity and freshness; return the provider signature timestamp."""

    @abstractmethod
    def parse_webhook(self, payload: dict[str, Any]) -> VideoMetadata:
        """Normalize a verified provider webhook payload."""
