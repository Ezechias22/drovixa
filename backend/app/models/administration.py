from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.content import Content


class HomepageSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "homepage_sections"
    __table_args__ = (
        CheckConstraint("max_items >= 1 AND max_items <= 50", name="max_items_range"),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at >= starts_at",
            name="schedule_range",
        ),
        Index("ix_homepage_sections_active_order", "active", "sort_order"),
    )

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(160))
    algorithm: Mapped[str] = mapped_column(String(50), index=True)
    presentation: Mapped[str] = mapped_column(String(30), default="poster", server_default="poster")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_items: Mapped[int] = mapped_column(Integer, default=20, server_default="20")
    genre_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("genres.id", ondelete="SET NULL"), index=True
    )
    target_countries: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    target_languages: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    target_subscription: Mapped[str | None] = mapped_column(String(30))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    items: Mapped[list[HomepageSectionItem]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="HomepageSectionItem.sort_order",
    )


class HomepageSectionItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "homepage_section_items"
    __table_args__ = (
        UniqueConstraint("section_id", "content_id", name="uq_homepage_section_content"),
        Index("ix_homepage_section_items_order", "section_id", "sort_order"),
    )

    section_id: Mapped[UUID] = mapped_column(
        ForeignKey("homepage_sections.id", ondelete="CASCADE"), index=True
    )
    content_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"), index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    section: Mapped[HomepageSection] = relationship(back_populates="items")
    content: Mapped[Content] = relationship(lazy="selectin")


class NotificationCampaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_campaigns"
    __table_args__ = (
        CheckConstraint("recipient_count >= 0", name="recipient_count_non_negative"),
        CheckConstraint("failure_count >= 0", name="failure_count_non_negative"),
        Index("ix_notification_campaigns_status_schedule", "status", "scheduled_at"),
    )

    name: Mapped[str] = mapped_column(String(160))
    type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(2048))
    action_url: Mapped[str | None] = mapped_column(String(2048))
    audience: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    channels: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    status: Mapped[str] = mapped_column(String(30), default="draft", server_default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    recipient_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    failure_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    campaign_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, server_default="{}"
    )
