from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import User


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    name: str
    status: str
    email_verified: bool
    country_code: str | None
    language_code: str | None
    avatar_url: str | None
    roles: list[str]
    created_at: datetime

    @classmethod
    def from_user(cls, user: User) -> UserOut:
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            status=user.status.value,
            email_verified=user.email_verified,
            country_code=user.country_code,
            language_code=user.language_code,
            avatar_url=user.avatar_url,
            roles=sorted(user.role_names),
            created_at=user.created_at,
        )


class UserUpdateInput(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    language_code: str | None = Field(default=None, min_length=2, max_length=16)

    @field_validator("country_code")
    @classmethod
    def normalize_country_code(cls, value: str | None) -> str | None:
        return value.upper() if value else None

    @field_validator("language_code")
    @classmethod
    def normalize_language_code(cls, value: str | None) -> str | None:
        return value.lower() if value else None


class AvatarUploadInput(BaseModel):
    mime_type: str = Field(pattern=r"^image/(jpeg|png|webp)$")
    base64_data: str = Field(min_length=16, max_length=2_600_000)


class DeviceOut(BaseModel):
    id: UUID
    device_id: str
    name: str
    platform: str
    last_ip: str | None
    last_seen_at: datetime
    current: bool = False
