from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.catalog import Actor, Country, CrewMember, Genre, Language, Tag
from app.models.enums import (
    AgeRating,
    ContentStatus,
    ContentType,
    ContentVisibility,
    EpisodeAccessType,
    Orientation,
    SeriesStatus,
    SubtitleFormat,
    VideoStatus,
)


def enum_values(enum: type[StrEnum]) -> list[str]:
    return [item.value for item in enum]


content_genres = Table(
    "content_genres",
    Base.metadata,
    Column("content_id", ForeignKey("content.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)

content_tags = Table(
    "content_tags",
    Base.metadata,
    Column("content_id", ForeignKey("content.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Content(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "content"
    __table_args__ = (
        CheckConstraint("rating >= 0 AND rating <= 10", name="rating_range"),
        CheckConstraint(
            "license_end IS NULL OR license_start IS NULL OR license_end >= license_start",
            name="license_date_range",
        ),
        Index("ix_content_feed", "status", "visibility", "type", "published_at"),
    )

    type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="content_type", values_callable=enum_values), index=True
    )
    title: Mapped[str] = mapped_column(String(240), index=True)
    slug: Mapped[str] = mapped_column(String(260), unique=True, index=True)
    original_title: Mapped[str | None] = mapped_column(String(240))
    short_description: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    poster_url: Mapped[str | None] = mapped_column(String(2048))
    backdrop_url: Mapped[str | None] = mapped_column(String(2048))
    trailer_url: Mapped[str | None] = mapped_column(String(2048))
    release_date: Mapped[date | None]
    country_id: Mapped[UUID | None] = mapped_column(ForeignKey("countries.id"), index=True)
    original_language_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("languages.id"), index=True
    )
    age_rating: Mapped[AgeRating] = mapped_column(
        Enum(AgeRating, name="age_rating", values_callable=enum_values),
        default=AgeRating.ALL,
        server_default=AgeRating.ALL.value,
    )
    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus, name="content_status", values_callable=enum_values),
        default=ContentStatus.DRAFT,
        server_default=ContentStatus.DRAFT.value,
        index=True,
    )
    visibility: Mapped[ContentVisibility] = mapped_column(
        Enum(ContentVisibility, name="content_visibility", values_callable=enum_values),
        default=ContentVisibility.PRIVATE,
        server_default=ContentVisibility.PRIVATE.value,
        index=True,
    )
    featured: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    premium: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    rating: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=0, server_default="0")
    view_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    like_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    license_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    license_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    allowed_countries: Mapped[list[str]] = mapped_column(JSON, default=list)
    blocked_countries: Mapped[list[str]] = mapped_column(JSON, default=list)
    seo_title: Mapped[str | None] = mapped_column(String(240))
    seo_description: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    country: Mapped[Country | None] = relationship(lazy="selectin")
    original_language: Mapped[Language | None] = relationship(lazy="selectin")
    genres: Mapped[list[Genre]] = relationship(secondary=content_genres, lazy="selectin")
    tags: Mapped[list[Tag]] = relationship(secondary=content_tags, lazy="selectin")
    actor_credits: Mapped[list[ContentActor]] = relationship(
        back_populates="content", cascade="all, delete-orphan", lazy="selectin"
    )
    crew_credits: Mapped[list[ContentCrew]] = relationship(
        back_populates="content", cascade="all, delete-orphan", lazy="selectin"
    )
    series: Mapped[Series | None] = relationship(
        back_populates="content", uselist=False, lazy="selectin"
    )
    movie: Mapped[Movie | None] = relationship(
        back_populates="content", uselist=False, lazy="selectin"
    )


class ContentActor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_actors"
    __table_args__ = (
        UniqueConstraint(
            "content_id",
            "actor_id",
            "character_name",
            name="uq_content_actors_credit",
        ),
    )

    content_id: Mapped[UUID] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("actors.id", ondelete="CASCADE"))
    character_name: Mapped[str] = mapped_column(String(180), default="")
    role: Mapped[str] = mapped_column(String(80), default="actor", server_default="actor")
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    content: Mapped[Content] = relationship(back_populates="actor_credits")
    actor: Mapped[Actor] = relationship(lazy="selectin")


class ContentCrew(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_crew"
    __table_args__ = (
        UniqueConstraint(
            "content_id",
            "crew_member_id",
            "role",
            name="uq_content_crew_credit",
        ),
    )

    content_id: Mapped[UUID] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"))
    crew_member_id: Mapped[UUID] = mapped_column(ForeignKey("crew_members.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    content: Mapped[Content] = relationship(back_populates="crew_credits")
    crew_member: Mapped[CrewMember] = relationship(lazy="selectin")


class Series(Base):
    __tablename__ = "series"

    id: Mapped[UUID] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"), primary_key=True)
    total_seasons: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    total_episodes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    series_status: Mapped[SeriesStatus] = mapped_column(
        Enum(SeriesStatus, name="series_status", values_callable=enum_values),
        default=SeriesStatus.DRAFT,
        server_default=SeriesStatus.DRAFT.value,
        index=True,
    )
    orientation: Mapped[Orientation] = mapped_column(
        Enum(Orientation, name="content_orientation", values_callable=enum_values),
        default=Orientation.HORIZONTAL,
        server_default=Orientation.HORIZONTAL.value,
    )

    content: Mapped[Content] = relationship(back_populates="series", lazy="selectin")
    seasons: Mapped[list[Season]] = relationship(
        back_populates="series", cascade="all, delete-orphan", lazy="selectin"
    )
    episodes: Mapped[list[Episode]] = relationship(back_populates="series", lazy="selectin")


class VideoAsset(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "video_assets"
    __table_args__ = (
        UniqueConstraint("provider", "provider_asset_id", name="provider_asset"),
        CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="duration"),
        CheckConstraint("width IS NULL OR width > 0", name="width"),
        CheckConstraint("height IS NULL OR height > 0", name="height"),
        Index("ix_video_assets_status_updated", "status", "updated_at"),
    )

    provider: Mapped[str] = mapped_column(String(80), index=True)
    provider_asset_id: Mapped[str] = mapped_column(String(255))
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus, name="video_status", values_callable=enum_values),
        default=VideoStatus.UPLOADING,
        server_default=VideoStatus.UPLOADING.value,
        index=True,
    )
    duration_seconds: Mapped[int | None]
    width: Mapped[int | None]
    height: Mapped[int | None]
    aspect_ratio: Mapped[str | None] = mapped_column(String(20))
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048))
    playback_id: Mapped[str | None] = mapped_column(String(255), index=True)
    provider_error_code: Mapped[str | None] = mapped_column(String(120))
    provider_error_message: Mapped[str | None] = mapped_column(Text)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    asset_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    subtitles: Mapped[list[Subtitle]] = relationship(
        back_populates="video_asset", cascade="all, delete-orphan", lazy="selectin"
    )


class Season(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("series_id", "season_number", name="number"),
        CheckConstraint("season_number > 0", name="number_positive"),
    )

    series_id: Mapped[UUID] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), index=True)
    season_number: Mapped[int]
    title: Mapped[str | None] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text)
    poster_url: Mapped[str | None] = mapped_column(String(2048))
    release_date: Mapped[date | None]
    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus, name="season_status", values_callable=enum_values),
        default=ContentStatus.DRAFT,
        server_default=ContentStatus.DRAFT.value,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    series: Mapped[Series] = relationship(back_populates="seasons")
    episodes: Mapped[list[Episode]] = relationship(back_populates="season", lazy="selectin")


class Episode(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "episodes"
    __table_args__ = (
        UniqueConstraint("series_id", "episode_number", name="series_number"),
        CheckConstraint("episode_number > 0", name="number_positive"),
        CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="duration"),
        CheckConstraint("coin_price >= 0", name="coin_price"),
        CheckConstraint(
            "free_until IS NULL OR free_from IS NULL OR free_until >= free_from",
            name="free_date_range",
        ),
    )

    series_id: Mapped[UUID] = mapped_column(ForeignKey("series.id", ondelete="CASCADE"), index=True)
    season_id: Mapped[UUID | None] = mapped_column(ForeignKey("seasons.id"), index=True)
    episode_number: Mapped[int]
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048))
    duration_seconds: Mapped[int | None]
    video_asset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("video_assets.id"), unique=True, index=True
    )
    orientation: Mapped[Orientation] = mapped_column(
        Enum(Orientation, name="episode_orientation", values_callable=enum_values),
        default=Orientation.HORIZONTAL,
        server_default=Orientation.HORIZONTAL.value,
    )
    access_type: Mapped[EpisodeAccessType] = mapped_column(
        Enum(EpisodeAccessType, name="episode_access_type", values_callable=enum_values),
        default=EpisodeAccessType.FREE,
        server_default=EpisodeAccessType.FREE.value,
    )
    coin_price: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    premium: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    free_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    free_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus, name="episode_status", values_callable=enum_values),
        default=ContentStatus.DRAFT,
        server_default=ContentStatus.DRAFT.value,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    series: Mapped[Series] = relationship(back_populates="episodes")
    season: Mapped[Season | None] = relationship(back_populates="episodes")
    video_asset: Mapped[VideoAsset | None] = relationship(lazy="selectin")


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        CheckConstraint("duration_seconds IS NULL OR duration_seconds >= 0", name="duration"),
        CheckConstraint("coin_price >= 0", name="coin_price"),
    )

    id: Mapped[UUID] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"), primary_key=True)
    duration_seconds: Mapped[int | None]
    video_asset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("video_assets.id"), unique=True, index=True
    )
    access_type: Mapped[EpisodeAccessType] = mapped_column(
        Enum(EpisodeAccessType, name="movie_access_type", values_callable=enum_values),
        default=EpisodeAccessType.FREE,
        server_default=EpisodeAccessType.FREE.value,
    )
    coin_price: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    content: Mapped[Content] = relationship(back_populates="movie", lazy="selectin")
    video_asset: Mapped[VideoAsset | None] = relationship(lazy="selectin")


class Subtitle(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "subtitles"
    __table_args__ = (UniqueConstraint("video_asset_id", "language_id", "label", name="track"),)

    video_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("video_assets.id", ondelete="CASCADE"), index=True
    )
    language_id: Mapped[UUID] = mapped_column(ForeignKey("languages.id"), index=True)
    label: Mapped[str] = mapped_column(String(120))
    format: Mapped[SubtitleFormat] = mapped_column(
        Enum(SubtitleFormat, name="subtitle_format", values_callable=enum_values)
    )
    file_url: Mapped[str] = mapped_column(String(2048))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_auto_generated: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    video_asset: Mapped[VideoAsset] = relationship(back_populates="subtitles")
    language: Mapped[Language] = relationship(lazy="selectin")
