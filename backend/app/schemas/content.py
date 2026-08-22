from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import (
    AgeRating,
    ContentVisibility,
    EpisodeAccessType,
    Orientation,
    SeriesStatus,
    SubtitleFormat,
    VideoStatus,
)


class ActorCreditInput(BaseModel):
    actor_id: UUID
    character_name: str = Field(default="", max_length=180)
    role: str = Field(default="actor", min_length=1, max_length=80)
    is_lead: bool = False
    sort_order: int = 0


class CrewCreditInput(BaseModel):
    crew_member_id: UUID
    role: str = Field(min_length=1, max_length=80)
    sort_order: int = 0


class RightsMixin(BaseModel):
    license_start: datetime | None = None
    license_end: datetime | None = None
    allowed_countries: list[str] = Field(default_factory=list, max_length=249)
    blocked_countries: list[str] = Field(default_factory=list, max_length=249)

    @field_validator("allowed_countries", "blocked_countries")
    @classmethod
    def normalize_countries(cls, value: list[str]) -> list[str]:
        normalized = [code.strip().upper() for code in value]
        if any(len(code) != 2 for code in normalized):
            raise ValueError("Country codes must use two ISO characters.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Country codes must be unique.")
        return normalized

    @model_validator(mode="after")
    def validate_rights(self) -> Self:
        if self.license_start and self.license_end and self.license_end < self.license_start:
            raise ValueError("license_end must be after license_start.")
        overlap = set(self.allowed_countries) & set(self.blocked_countries)
        if overlap:
            raise ValueError("A country cannot be both allowed and blocked.")
        return self


class ContentCommonCreate(RightsMixin):
    title: str = Field(min_length=1, max_length=240)
    slug: str | None = Field(default=None, min_length=1, max_length=260)
    original_title: str | None = Field(default=None, max_length=240)
    short_description: str | None = Field(default=None, max_length=500)
    description: str | None = None
    poster_url: str | None = Field(default=None, max_length=2048)
    backdrop_url: str | None = Field(default=None, max_length=2048)
    trailer_url: str | None = Field(default=None, max_length=2048)
    release_date: date | None = None
    country_id: UUID | None = None
    original_language_id: UUID | None = None
    age_rating: AgeRating = AgeRating.ALL
    visibility: ContentVisibility = ContentVisibility.PRIVATE
    featured: bool = False
    premium: bool = False
    rating: Decimal = Field(default=Decimal("0"), ge=0, le=10, decimal_places=2)
    seo_title: str | None = Field(default=None, max_length=240)
    seo_description: str | None = Field(default=None, max_length=500)
    genre_ids: list[UUID] = Field(default_factory=list)
    tag_ids: list[UUID] = Field(default_factory=list)
    actor_credits: list[ActorCreditInput] = Field(default_factory=list)
    crew_credits: list[CrewCreditInput] = Field(default_factory=list)


class SeriesCreate(ContentCommonCreate):
    series_status: SeriesStatus = SeriesStatus.DRAFT
    orientation: Orientation = Orientation.HORIZONTAL


class MovieCreate(ContentCommonCreate):
    duration_seconds: int | None = Field(default=None, ge=0)
    video_asset_id: UUID | None = None
    access_type: EpisodeAccessType = EpisodeAccessType.FREE
    coin_price: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_coin_price(self) -> Self:
        if (
            self.access_type
            in {
                EpisodeAccessType.COIN_UNLOCK,
                EpisodeAccessType.PREMIUM_OR_COIN,
            }
            and self.coin_price < 1
        ):
            raise ValueError("coin_price must be positive for coin access.")
        return self


class ContentCommonUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    slug: str | None = Field(default=None, min_length=1, max_length=260)
    original_title: str | None = Field(default=None, max_length=240)
    short_description: str | None = Field(default=None, max_length=500)
    description: str | None = None
    poster_url: str | None = Field(default=None, max_length=2048)
    backdrop_url: str | None = Field(default=None, max_length=2048)
    trailer_url: str | None = Field(default=None, max_length=2048)
    release_date: date | None = None
    country_id: UUID | None = None
    original_language_id: UUID | None = None
    age_rating: AgeRating | None = None
    visibility: ContentVisibility | None = None
    featured: bool | None = None
    premium: bool | None = None
    rating: Decimal | None = Field(default=None, ge=0, le=10, decimal_places=2)
    license_start: datetime | None = None
    license_end: datetime | None = None
    allowed_countries: list[str] | None = Field(default=None, max_length=249)
    blocked_countries: list[str] | None = Field(default=None, max_length=249)
    seo_title: str | None = Field(default=None, max_length=240)
    seo_description: str | None = Field(default=None, max_length=500)
    genre_ids: list[UUID] | None = None
    tag_ids: list[UUID] | None = None
    actor_credits: list[ActorCreditInput] | None = None
    crew_credits: list[CrewCreditInput] | None = None

    @field_validator("allowed_countries", "blocked_countries")
    @classmethod
    def normalize_countries(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [code.strip().upper() for code in value]
        if any(len(code) != 2 for code in normalized):
            raise ValueError("Country codes must use two ISO characters.")
        if len(normalized) != len(set(normalized)):
            raise ValueError("Country codes must be unique.")
        return normalized


class SeriesUpdate(ContentCommonUpdate):
    series_status: SeriesStatus | None = None
    orientation: Orientation | None = None


class MovieUpdate(ContentCommonUpdate):
    duration_seconds: int | None = Field(default=None, ge=0)
    video_asset_id: UUID | None = None
    access_type: EpisodeAccessType | None = None
    coin_price: int | None = Field(default=None, ge=0)


class SeasonCreate(BaseModel):
    series_id: UUID
    season_number: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=240)
    description: str | None = None
    poster_url: str | None = Field(default=None, max_length=2048)
    release_date: date | None = None
    sort_order: int = 0


class SeasonUpdate(BaseModel):
    season_number: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, max_length=240)
    description: str | None = None
    poster_url: str | None = Field(default=None, max_length=2048)
    release_date: date | None = None
    sort_order: int | None = None


class EpisodeCreate(BaseModel):
    series_id: UUID
    season_id: UUID | None = None
    episode_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=240)
    description: str | None = None
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    duration_seconds: int | None = Field(default=None, ge=0)
    video_asset_id: UUID | None = None
    orientation: Orientation = Orientation.HORIZONTAL
    access_type: EpisodeAccessType = EpisodeAccessType.FREE
    coin_price: int = Field(default=0, ge=0)
    premium: bool = False
    free_from: datetime | None = None
    free_until: datetime | None = None
    sort_order: int = 0

    @model_validator(mode="after")
    def validate_access(self) -> Self:
        if self.free_from and self.free_until and self.free_until < self.free_from:
            raise ValueError("free_until must be after free_from.")
        if (
            self.access_type
            in {
                EpisodeAccessType.COIN_UNLOCK,
                EpisodeAccessType.PREMIUM_OR_COIN,
            }
            and self.coin_price < 1
        ):
            raise ValueError("coin_price must be positive for coin access.")
        return self


class EpisodeUpdate(BaseModel):
    season_id: UUID | None = None
    episode_number: int | None = Field(default=None, ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    duration_seconds: int | None = Field(default=None, ge=0)
    video_asset_id: UUID | None = None
    orientation: Orientation | None = None
    access_type: EpisodeAccessType | None = None
    coin_price: int | None = Field(default=None, ge=0)
    premium: bool | None = None
    free_from: datetime | None = None
    free_until: datetime | None = None
    sort_order: int | None = None


class VideoAssetCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    provider_asset_id: str = Field(min_length=1, max_length=255)
    status: VideoStatus = VideoStatus.UPLOADING
    duration_seconds: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    aspect_ratio: str | None = Field(default=None, max_length=20)
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    playback_id: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VideoAssetUpdate(BaseModel):
    status: VideoStatus | None = None
    duration_seconds: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    aspect_ratio: str | None = Field(default=None, max_length=20)
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    playback_id: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] | None = None


class SubtitleCreate(BaseModel):
    video_asset_id: UUID
    language_id: UUID
    label: str = Field(min_length=1, max_length=120)
    format: SubtitleFormat
    file_url: str = Field(min_length=1, max_length=2048)
    is_default: bool = False
    is_auto_generated: bool = False


class SubtitleUpdate(BaseModel):
    language_id: UUID | None = None
    label: str | None = Field(default=None, min_length=1, max_length=120)
    format: SubtitleFormat | None = None
    file_url: str | None = Field(default=None, min_length=1, max_length=2048)
    is_default: bool | None = None
    is_auto_generated: bool | None = None
