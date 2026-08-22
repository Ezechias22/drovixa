from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.content import Content


class Favorite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "content_id", name="uq_favorites_user_content"),
        Index("ix_favorites_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[Content] = relationship(lazy="selectin")


class SearchHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "search_history"
    __table_args__ = (
        Index("ix_search_history_user_recent", "user_id", "updated_at"),
        Index("ix_search_history_query_recent", "normalized_query", "updated_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    query: Mapped[str] = mapped_column(String(160))
    normalized_query: Mapped[str] = mapped_column(String(160))


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_user_unread", "user_id", "read_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    action_url: Mapped[str | None] = mapped_column(String(2048))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class NotificationPreference(TimestampMixin, Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    new_episodes: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    promotions: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    recommendations: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    wallet: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    comments: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    security: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
