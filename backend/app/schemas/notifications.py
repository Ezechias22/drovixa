from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PushTokenRegistration(BaseModel):
    provider: Literal["fcm"] = "fcm"
    platform: Literal["android", "ios", "web"]
    token: str = Field(min_length=20, max_length=8_192)
    app_version: str | None = Field(default=None, max_length=40)
    locale: str | None = Field(default=None, max_length=20)

    @field_validator("token")
    @classmethod
    def clean_token(cls, value: str) -> str:
        return value.strip()

    @field_validator("locale")
    @classmethod
    def clean_locale(cls, value: str | None) -> str | None:
        return value.strip().lower() if value else None
