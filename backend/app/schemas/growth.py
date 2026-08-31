from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.auth import DeviceInput


class AdEventInput(BaseModel):
    delivery_id: UUID
    session_key: str = Field(min_length=20, max_length=96)
    event_type: Literal["impression", "click", "completed"]


class RewardedAdSessionInput(BaseModel):
    platform: Literal["android", "ios"]


class ReferralApplyInput(BaseModel):
    code: str = Field(min_length=4, max_length=20, pattern=r"^[A-Za-z0-9]+$")


class SocialLoginInput(BaseModel):
    provider: Literal["google", "apple"]
    id_token: str = Field(min_length=40, max_length=10000)
    device: DeviceInput
    display_name: str | None = Field(default=None, max_length=120)


class WatchPartyCreateInput(BaseModel):
    content_id: UUID
    episode_id: UUID | None = None
    profile_id: UUID | None = None
    title: str = Field(min_length=1, max_length=180)
    max_members: int = Field(default=10, ge=2, le=25)


class WatchPartyJoinInput(BaseModel):
    profile_id: UUID | None = None


class WatchPartyStateInput(BaseModel):
    position_seconds: int = Field(ge=0)
    paused: bool
    status: Literal["lobby", "playing", "paused", "ended"]


class WatchPartyMessageInput(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class GrowthEventInput(BaseModel):
    event_name: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9_.-]+$")
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class AdPlacementInput(BaseModel):
    key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=160)
    placement: str = Field(min_length=2, max_length=80)
    format: Literal["card", "banner", "rewarded_video"] = "card"
    headline: str = Field(min_length=2, max_length=180)
    body: str | None = Field(default=None, max_length=2000)
    media_url: str | None = Field(default=None, max_length=2000)
    click_url: str | None = Field(default=None, max_length=1000)
    sponsor: str | None = Field(default=None, max_length=120)
    reward_coins: int = Field(default=0, ge=0, le=10000)
    daily_cap: int = Field(default=3, ge=1, le=100)
    priority: int = Field(default=0, ge=-10000, le=10000)
    active: bool = True


class GrowthAutomationUpdate(BaseModel):
    active: bool | None = None
    cooldown_hours: int | None = Field(default=None, ge=0, le=8760)


class EngagementConfigUpdate(BaseModel):
    rewarded_ads_enabled: bool
    premium_offers_enabled: bool
    content_notifications_enabled: bool
    continue_watching_reminders_enabled: bool
    coins_per_ad: int = Field(ge=1, le=100)
    daily_limit: int = Field(ge=1, le=25)
    max_per_session: int = Field(ge=0, le=3)
    max_per_day: int = Field(ge=0, le=5)
    first_delay_seconds: int = Field(ge=30, le=3600)
    repeat_delay_seconds: int = Field(ge=180, le=7200)
    premium_notification_cooldown_hours: int = Field(ge=24, le=168)
    continue_after_hours: int = Field(ge=6, le=168)
    continue_cooldown_hours: int = Field(ge=12, le=336)


class SocialClaims(BaseModel):
    subject: str
    email: EmailStr
    name: str | None = None
