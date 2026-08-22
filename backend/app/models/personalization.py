from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ViewerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "viewer_profiles"
    __table_args__ = (
        CheckConstraint("age_limit >= 0 AND age_limit <= 18", name="age_limit_range"),
        Index("ix_viewer_profiles_user_active", "user_id", "active"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    avatar_key: Mapped[str] = mapped_column(String(60), default="nova", server_default="nova")
    is_kids: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    age_limit: Mapped[int] = mapped_column(Integer, default=18, server_default="18")
    language_code: Mapped[str] = mapped_column(String(16), default="en", server_default="en")
    autoplay_next: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    autoplay_previews: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    pin_hash: Mapped[str | None] = mapped_column(String(512))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ContentRating(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_ratings"
    __table_args__ = (
        UniqueConstraint("profile_id", "content_id", name="uq_content_ratings_profile_content"),
        CheckConstraint("score >= 1 AND score <= 5", name="score_range"),
        Index("ix_content_ratings_content", "content_id", "score"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("viewer_profiles.id", ondelete="CASCADE"), index=True
    )
    content_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[int] = mapped_column(Integer)


class DownloadLicense(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "download_licenses"
    __table_args__ = (
        CheckConstraint("bytes_downloaded >= 0", name="bytes_non_negative"),
        Index("ix_download_licenses_user_status", "user_id", "status"),
        Index("ix_download_licenses_expiry", "expires_at", "revoked_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("viewer_profiles.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    content_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), index=True
    )
    video_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("video_assets.id", ondelete="CASCADE"), index=True
    )
    quality: Mapped[str] = mapped_column(String(30), default="720p", server_default="720p")
    status: Mapped[str] = mapped_column(
        String(30), default="authorized", server_default="authorized", index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bytes_downloaded: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")

    profile: Mapped[ViewerProfile] = relationship(lazy="joined")


class CastSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cast_sessions"
    __table_args__ = (Index("ix_cast_sessions_user_status", "user_id", "status"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("viewer_profiles.id", ondelete="CASCADE"), index=True
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    playback_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("playback_sessions.id", ondelete="SET NULL"), index=True
    )
    target_device_id: Mapped[str] = mapped_column(String(200))
    target_device_name: Mapped[str] = mapped_column(String(160))
    target_type: Mapped[str] = mapped_column(String(30), default="chromecast")
    status: Mapped[str] = mapped_column(String(30), default="connected", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
