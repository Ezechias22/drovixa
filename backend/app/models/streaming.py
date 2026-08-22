from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.content import Content, Episode, VideoAsset, enum_values
from app.models.enums import (
    ContentType,
    UploadProtocol,
    WebhookProcessingStatus,
)


class VideoUploadSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "video_upload_sessions"

    video_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("video_assets.id", ondelete="CASCADE"), unique=True, index=True
    )
    initiated_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    protocol: Mapped[UploadProtocol] = mapped_column(
        Enum(UploadProtocol, name="upload_protocol", values_callable=enum_values)
    )
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    file_size_bytes: Mapped[int] = mapped_column(BigInteger)
    max_duration_seconds: Mapped[int]
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    upload_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    video_asset: Mapped[VideoAsset] = relationship(lazy="joined")


class VideoWebhookEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "video_webhook_events"
    __table_args__ = (
        UniqueConstraint("provider", "idempotency_key", name="uq_video_webhook_event"),
    )

    provider: Mapped[str] = mapped_column(String(80), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    provider_asset_id: Mapped[str | None] = mapped_column(String(255), index=True)
    event_type: Mapped[str] = mapped_column(String(120))
    signature_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[WebhookProcessingStatus] = mapped_column(
        Enum(
            WebhookProcessingStatus,
            name="webhook_processing_status",
            values_callable=enum_values,
        ),
        default=WebhookProcessingStatus.RECEIVED,
        server_default=WebhookProcessingStatus.RECEIVED.value,
        index=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class UserEntitlement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_entitlements"
    __table_args__ = (
        Index("ix_user_entitlements_lookup", "user_id", "content_id", "episode_id"),
        CheckConstraint(
            "expires_at IS NULL OR starts_at IS NULL OR expires_at >= starts_at",
            name="date_range",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="entitlement_content_type", values_callable=enum_values)
    )
    content_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(80))
    transaction_id: Mapped[UUID | None] = mapped_column(index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    is_permanent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class PlaybackSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "playback_sessions"
    __table_args__ = (
        Index("ix_playback_sessions_user_active", "user_id", "expires_at", "revoked_at"),
        Index("ix_playback_sessions_asset_active", "video_asset_id", "expires_at"),
    )

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    auth_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("user_sessions.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    client_device_id: Mapped[str] = mapped_column(String(160))
    content_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), index=True
    )
    video_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("video_assets.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(80))
    country_code: Mapped[str | None] = mapped_column(String(2))
    ip: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    view_counted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    content: Mapped[Content] = relationship(lazy="selectin")
    episode: Mapped[Episode | None] = relationship(lazy="selectin")
    video_asset: Mapped[VideoAsset] = relationship(lazy="joined")


class WatchProgress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "watch_progress"
    __table_args__ = (
        CheckConstraint("position_seconds >= 0", name="position_non_negative"),
        CheckConstraint("duration_seconds > 0", name="duration_positive"),
        CheckConstraint("percentage >= 0 AND percentage <= 100", name="percentage_range"),
        Index(
            "uq_watch_progress_episode",
            "user_id",
            "episode_id",
            unique=True,
            postgresql_where=text("episode_id IS NOT NULL"),
            sqlite_where=text("episode_id IS NOT NULL"),
        ),
        Index(
            "uq_watch_progress_movie",
            "user_id",
            "content_id",
            unique=True,
            postgresql_where=text("episode_id IS NULL"),
            sqlite_where=text("episode_id IS NULL"),
        ),
        Index("ix_watch_progress_continue", "user_id", "completed", "removed_at"),
        Index("ix_watch_progress_user_watched", "user_id", "last_watched_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="watch_content_type", values_callable=enum_values)
    )
    content_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    position_seconds: Mapped[int]
    duration_seconds: Mapped[int]
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    last_watched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    content: Mapped[Content] = relationship(lazy="selectin")
    episode: Mapped[Episode | None] = relationship(lazy="selectin")


class WatchHistory(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "watch_history"
    __table_args__ = (
        UniqueConstraint("playback_session_id", name="uq_watch_history_playback_session"),
        Index("ix_watch_history_user_watched", "user_id", "last_watched_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="history_content_type", values_callable=enum_values)
    )
    content_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), index=True
    )
    playback_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("playback_sessions.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    position_seconds: Mapped[int]
    duration_seconds: Mapped[int]
    percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    completed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_watched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    content: Mapped[Content] = relationship(lazy="selectin")
    episode: Mapped[Episode | None] = relationship(lazy="selectin")
