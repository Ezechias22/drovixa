from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class PushToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "push_tokens"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "device_id", "provider", name="uq_push_tokens_user_device_provider"
        ),
        Index("ix_push_tokens_active_provider", "active", "provider"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    device_id: Mapped[str] = mapped_column(String(160), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default="fcm", nullable=False)
    platform: Mapped[str] = mapped_column(String(30), nullable=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    active: Mapped[bool] = mapped_column(default=True, nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_count: Mapped[int] = mapped_column(default=0, nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "push_token_id",
            "channel",
            name="uq_notification_deliveries_campaign_token_channel",
        ),
        Index("ix_notification_deliveries_campaign_status", "campaign_id", "status"),
    )

    campaign_id: Mapped[UUID] = mapped_column(
        ForeignKey("notification_campaigns.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    push_token_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("push_tokens.id", ondelete="SET NULL"), index=True, nullable=True
    )
    channel: Mapped[str] = mapped_column(String(30), default="push", nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default="fcm", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(160), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1_000), nullable=True)
    attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
