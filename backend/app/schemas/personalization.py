from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    avatar_key: str = Field(default="nova", min_length=1, max_length=60)
    is_kids: bool = False
    age_limit: int = Field(default=18, ge=0, le=18)
    language_code: str = Field(default="en", min_length=2, max_length=16)
    pin: str | None = Field(default=None, pattern=r"^\d{4,6}$")
    autoplay_next: bool = True
    autoplay_previews: bool = True

    @model_validator(mode="after")
    def normalize_kids_limit(self) -> ProfileCreate:
        if self.is_kids and self.age_limit > 13:
            self.age_limit = 13
        return self

    @field_validator("name", "avatar_key", "language_code")
    @classmethod
    def trim_strings(cls, value: str) -> str:
        return value.strip()


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_key: str | None = Field(default=None, min_length=1, max_length=60)
    is_kids: bool | None = None
    age_limit: int | None = Field(default=None, ge=0, le=18)
    language_code: str | None = Field(default=None, min_length=2, max_length=16)
    pin: str | None = Field(default=None, pattern=r"^\d{4,6}$")
    clear_pin: bool = False
    autoplay_next: bool | None = None
    autoplay_previews: bool | None = None


class ProfilePinVerify(BaseModel):
    pin: str = Field(pattern=r"^\d{4,6}$")


class RatingInput(BaseModel):
    score: int = Field(ge=1, le=5)


class DownloadAuthorizeInput(BaseModel):
    profile_id: UUID | None = None
    quality: Literal["highest", "1080p", "720p", "540p", "480p", "360p"] = "720p"


class DownloadStatusInput(BaseModel):
    status: Literal["downloading", "ready", "failed", "deleted"]
    bytes_downloaded: int = Field(default=0, ge=0)


class CastSessionInput(BaseModel):
    profile_id: UUID | None = None
    playback_session_id: UUID | None = None
    target_device_id: str = Field(min_length=1, max_length=200)
    target_device_name: str = Field(min_length=1, max_length=160)
    target_type: Literal["chromecast", "airplay"] = "chromecast"


class CastHeartbeatInput(BaseModel):
    status: Literal["connected", "playing", "paused", "ended"] = "connected"
