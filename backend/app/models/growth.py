from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AdPlacement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ad_placements"
    __table_args__ = (
        CheckConstraint("reward_coins >= 0", name="reward_coins_non_negative"),
        CheckConstraint("daily_cap >= 1", name="daily_cap_positive"),
        Index("ix_ad_placements_placement_active", "placement", "active"),
    )

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    placement: Mapped[str] = mapped_column(String(80), index=True)
    format: Mapped[str] = mapped_column(String(30), default="card", server_default="card")
    headline: Mapped[str] = mapped_column(String(180))
    body: Mapped[str | None] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(String(2000))
    click_url: Mapped[str | None] = mapped_column(String(1000))
    sponsor: Mapped[str | None] = mapped_column(String(120))
    countries: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    languages: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    reward_coins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    daily_cap: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)


class AdDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ad_deliveries"
    __table_args__ = (Index("ix_ad_deliveries_user_created", "user_id", "created_at"),)

    ad_id: Mapped[UUID] = mapped_column(
        ForeignKey("ad_placements.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    device_key: Mapped[str] = mapped_column(String(180), index=True)
    session_key: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ad_events"
    __table_args__ = (
        UniqueConstraint("delivery_id", "event_type", name="uq_ad_events_delivery_event"),
        Index("ix_ad_events_ad_created", "ad_id", "created_at"),
    )

    ad_id: Mapped[UUID] = mapped_column(
        ForeignKey("ad_placements.id", ondelete="CASCADE"), index=True
    )
    delivery_id: Mapped[UUID] = mapped_column(
        ForeignKey("ad_deliveries.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(30), index=True)


class RewardedAdSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rewarded_ad_sessions"
    __table_args__ = (
        CheckConstraint("reward_coins > 0", name="rewarded_ad_coins_positive"),
        UniqueConstraint("session_token", name="uq_rewarded_ad_session_token"),
        UniqueConstraint("admob_transaction_id", name="uq_rewarded_ad_transaction"),
        Index("ix_rewarded_ad_user_created", "user_id", "created_at"),
        Index("ix_rewarded_ad_status_expires", "status", "expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    session_token: Mapped[str] = mapped_column(String(96))
    platform: Mapped[str] = mapped_column(String(20))
    ad_unit_id: Mapped[str] = mapped_column(String(160))
    reward_coins: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="pending", server_default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    admob_transaction_id: Mapped[str | None] = mapped_column(String(200))
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    verification_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default="{}"
    )


class DailyRewardClaim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_reward_claims"
    __table_args__ = (
        UniqueConstraint("user_id", "claim_date", name="uq_daily_reward_user_date"),
        CheckConstraint("coins > 0", name="daily_reward_coins_positive"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    claim_date: Mapped[date] = mapped_column(Date, index=True)
    streak_day: Mapped[int] = mapped_column(Integer)
    coins: Mapped[int] = mapped_column(Integer)
    ledger_id: Mapped[UUID] = mapped_column(
        ForeignKey("wallet_ledger.id", ondelete="RESTRICT"), unique=True
    )


class ReferralCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "referral_codes"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Referral(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("invitee_id", name="uq_referrals_invitee"),
        CheckConstraint("inviter_reward >= 0", name="inviter_reward_non_negative"),
        CheckConstraint("invitee_reward >= 0", name="invitee_reward_non_negative"),
    )

    inviter_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invitee_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code_id: Mapped[UUID] = mapped_column(
        ForeignKey("referral_codes.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="qualified", server_default="qualified")
    inviter_reward: Mapped[int] = mapped_column(Integer, default=50, server_default="50")
    invitee_reward: Mapped[int] = mapped_column(Integer, default=25, server_default="25")
    qualified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SocialIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "social_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_social_identity_provider_subject"),
        UniqueConstraint("user_id", "provider", name="uq_social_identity_user_provider"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(30), index=True)
    subject: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)


class WatchParty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "watch_parties"
    __table_args__ = (
        CheckConstraint("position_seconds >= 0", name="watch_party_position_non_negative"),
        CheckConstraint("max_members >= 2 AND max_members <= 25", name="max_members_range"),
        Index("ix_watch_parties_host_status", "host_id", "status"),
    )

    host_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content_id: Mapped[UUID] = mapped_column(
        ForeignKey("content.id", ondelete="CASCADE"), index=True
    )
    episode_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("episodes.id", ondelete="CASCADE"), index=True
    )
    invite_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(30), default="lobby", server_default="lobby")
    position_seconds: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    paused: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    max_members: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WatchPartyMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "watch_party_members"
    __table_args__ = (
        UniqueConstraint("party_id", "user_id", name="uq_watch_party_member_user"),
        Index("ix_watch_party_members_party_status", "party_id", "status"),
    )

    party_id: Mapped[UUID] = mapped_column(
        ForeignKey("watch_parties.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("viewer_profiles.id", ondelete="SET NULL"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="guest", server_default="guest")
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class WatchPartyMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "watch_party_messages"
    __table_args__ = (Index("ix_watch_party_messages_party_created", "party_id", "created_at"),)

    party_id: Mapped[UUID] = mapped_column(
        ForeignKey("watch_parties.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message: Mapped[str] = mapped_column(String(500))


class GrowthAutomation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "growth_automations"

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    trigger_event: Mapped[str] = mapped_column(String(80), index=True)
    action_type: Mapped[str] = mapped_column(String(40), default="notification")
    action_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    cooldown_hours: Mapped[int] = mapped_column(Integer, default=24, server_default="24")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GrowthEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "growth_events"
    __table_args__ = (Index("ix_growth_events_name_created", "event_name", "created_at"),)

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_name: Mapped[str] = mapped_column(String(80), index=True)
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, server_default="{}"
    )
