from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import UserStatus

HomepageAlgorithm = Literal[
    "manual",
    "trending",
    "latest",
    "most_watched",
    "recommended",
    "genre",
    "continue_watching",
    "top_10",
    "recently_added",
]
HomepagePresentation = Literal["poster", "wide", "ranked", "progress"]


class HomepageSectionCreate(BaseModel):
    key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9_]+$")
    title: str = Field(min_length=2, max_length=160)
    algorithm: HomepageAlgorithm
    presentation: HomepagePresentation = "poster"
    active: bool = True
    sort_order: int = Field(default=0, ge=0, le=10_000)
    max_items: int = Field(default=20, ge=1, le=50)
    genre_id: UUID | None = None
    target_countries: list[str] = Field(default_factory=list, max_length=250)
    target_languages: list[str] = Field(default_factory=list, max_length=250)
    target_subscription: Literal["premium", "non_premium"] | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @field_validator("target_countries")
    @classmethod
    def normalize_countries(cls, value: list[str]) -> list[str]:
        normalized = sorted({item.strip().upper() for item in value if item.strip()})
        if any(not re.fullmatch(r"[A-Z]{2}", item) for item in normalized):
            raise ValueError("Country codes must use ISO alpha-2 format")
        return normalized

    @field_validator("target_languages")
    @classmethod
    def normalize_languages(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().lower() for item in value if item.strip()})

    @model_validator(mode="after")
    def validate_section(self) -> HomepageSectionCreate:
        if self.ends_at and self.starts_at and self.ends_at < self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        if self.algorithm == "genre" and self.genre_id is None:
            raise ValueError("genre_id is required for the genre algorithm")
        return self


class HomepageSectionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    algorithm: HomepageAlgorithm | None = None
    presentation: HomepagePresentation | None = None
    active: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)
    max_items: int | None = Field(default=None, ge=1, le=50)
    genre_id: UUID | None = None
    target_countries: list[str] | None = Field(default=None, max_length=250)
    target_languages: list[str] | None = Field(default=None, max_length=250)
    target_subscription: Literal["premium", "non_premium"] | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @field_validator("target_countries")
    @classmethod
    def normalize_countries(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = sorted({item.strip().upper() for item in value if item.strip()})
        if any(not re.fullmatch(r"[A-Z]{2}", item) for item in normalized):
            raise ValueError("Country codes must use ISO alpha-2 format")
        return normalized

    @field_validator("target_languages")
    @classmethod
    def normalize_languages(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return sorted({item.strip().lower() for item in value if item.strip()})


class HomepageItemCreate(BaseModel):
    content_id: UUID
    sort_order: int = Field(default=0, ge=0, le=10_000)


class HomepageReorderInput(BaseModel):
    section_ids: list[UUID] = Field(min_length=1, max_length=100)


class AdminUserStatusUpdate(BaseModel):
    status: UserStatus
    reason: str = Field(min_length=3, max_length=500)


class AdminUserRolesUpdate(BaseModel):
    roles: list[str] = Field(min_length=1, max_length=10)

    @field_validator("roles")
    @classmethod
    def normalize_roles(cls, value: list[str]) -> list[str]:
        return sorted({item.strip().lower() for item in value if item.strip()})


CampaignSegment = Literal[
    "all",
    "premium",
    "non_premium",
    "country",
    "language",
    "inactive",
    "specific",
]
CampaignChannel = Literal["in_app", "push", "email"]


def default_campaign_channels() -> list[CampaignChannel]:
    return ["in_app"]


class CampaignAudience(BaseModel):
    segment: CampaignSegment = "all"
    user_ids: list[UUID] = Field(default_factory=list, max_length=5_000)
    country_codes: list[str] = Field(default_factory=list, max_length=250)
    language_codes: list[str] = Field(default_factory=list, max_length=250)
    inactive_days: int = Field(default=30, ge=1, le=3_650)

    @model_validator(mode="after")
    def validate_target(self) -> CampaignAudience:
        required = {
            "specific": bool(self.user_ids),
            "country": bool(self.country_codes),
            "language": bool(self.language_codes),
        }
        if self.segment in required and not required[self.segment]:
            raise ValueError(f"Audience data is required for segment {self.segment}")
        self.country_codes = sorted({item.upper() for item in self.country_codes})
        self.language_codes = sorted({item.lower() for item in self.language_codes})
        return self


class NotificationCampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    type: Literal[
        "new_episode",
        "new_series",
        "promotion",
        "wallet",
        "purchase",
        "subscription",
        "system",
        "recommendation",
        "comment_reply",
        "comment_like",
        "account_security",
    ]
    title: str = Field(min_length=2, max_length=240)
    body: str = Field(min_length=2, max_length=2_000)
    image_url: str | None = Field(default=None, max_length=2_048)
    action_url: str | None = Field(default=None, max_length=2_048)
    audience: CampaignAudience = Field(default_factory=CampaignAudience)
    channels: list[CampaignChannel] = Field(default_factory=default_campaign_channels, min_length=1)
    scheduled_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationCampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    title: str | None = Field(default=None, min_length=2, max_length=240)
    body: str | None = Field(default=None, min_length=2, max_length=2_000)
    image_url: str | None = Field(default=None, max_length=2_048)
    action_url: str | None = Field(default=None, max_length=2_048)
    audience: CampaignAudience | None = None
    channels: list[CampaignChannel] | None = Field(default=None, min_length=1)
    scheduled_at: datetime | None = None
    metadata: dict[str, Any] | None = None


class NotificationCampaignSendInput(BaseModel):
    send_now: bool = True
