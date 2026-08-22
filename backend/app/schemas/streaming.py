from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import get_settings

ALLOWED_VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-matroska",
    "video/webm",
    "video/x-m4v",
}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


class UploadSessionCreate(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=3, max_length=120)
    file_size_bytes: int = Field(gt=0)
    max_duration_seconds: int = Field(ge=1)
    protocol: Literal["auto", "basic", "tus", "resumable"] = "auto"

    @field_validator("file_name")
    @classmethod
    def validate_extension(cls, value: str) -> str:
        clean = value.strip()
        suffix = "." + clean.rsplit(".", maxsplit=1)[-1].casefold() if "." in clean else ""
        if suffix not in ALLOWED_VIDEO_EXTENSIONS:
            raise ValueError("Unsupported video file extension")
        return clean

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str) -> str:
        normalized = value.casefold().strip()
        if normalized not in ALLOWED_VIDEO_MIME_TYPES:
            raise ValueError("Unsupported video MIME type")
        return normalized

    @model_validator(mode="after")
    def validate_limits(self) -> UploadSessionCreate:
        settings = get_settings()
        if self.file_size_bytes > settings.VIDEO_UPLOAD_MAX_BYTES:
            raise ValueError("Video file exceeds the configured upload limit")
        if self.max_duration_seconds > settings.VIDEO_UPLOAD_MAX_DURATION_SECONDS:
            raise ValueError("Video duration exceeds the configured upload limit")
        if self.protocol == "basic" and self.file_size_bytes > 200 * 1024 * 1024:
            raise ValueError("Basic upload cannot be used for files larger than 200 MB")
        return self


class SourceVideoIngestCreate(BaseModel):
    source_url: str = Field(pattern=r"^https://", max_length=2048)
    file_name: str = Field(min_length=1, max_length=255)


class PlaybackAuthorizeInput(BaseModel):
    client_device_id: str | None = Field(default=None, min_length=8, max_length=160)


class ProgressSyncInput(BaseModel):
    playback_session_id: UUID
    position_seconds: int = Field(ge=0)
    duration_seconds: int = Field(gt=0)


class HistoryClearInput(BaseModel):
    confirmation: Literal["clear"]
