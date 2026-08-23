"""phase 11 ads, rewards, referrals, social login and watch parties

Revision ID: 20260825_0012
Revises: 20260824_0011
Create Date: 2026-08-25 00:12:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0012"
down_revision: str | None = "20260824_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ad_placements",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("placement", sa.String(length=80), nullable=False),
        sa.Column("format", sa.String(length=30), server_default="card", nullable=False),
        sa.Column("headline", sa.String(length=180), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("media_url", sa.String(length=2000), nullable=True),
        sa.Column("click_url", sa.String(length=1000), nullable=True),
        sa.Column("sponsor", sa.String(length=120), nullable=True),
        sa.Column("countries", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("languages", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("reward_coins", sa.Integer(), server_default="0", nullable=False),
        sa.Column("daily_cap", sa.Integer(), server_default="3", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("daily_cap >= 1", name="ck_ad_placements_daily_cap_positive"),
        sa.CheckConstraint("reward_coins >= 0", name="ck_ad_placements_reward_coins_non_negative"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_ad_placements_key"),
    )
    for column in ("key", "placement", "starts_at", "ends_at", "active"):
        op.create_index(f"ix_ad_placements_{column}", "ad_placements", [column])
    op.create_index("ix_ad_placements_placement_active", "ad_placements", ["placement", "active"])

    op.create_table(
        "ad_deliveries",
        sa.Column("ad_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("device_key", sa.String(length=180), nullable=False),
        sa.Column("session_key", sa.String(length=96), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ad_id"], ["ad_placements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_key", name="uq_ad_deliveries_session_key"),
    )
    for column in ("ad_id", "user_id", "device_key", "session_key", "expires_at"):
        op.create_index(f"ix_ad_deliveries_{column}", "ad_deliveries", [column])
    op.create_index("ix_ad_deliveries_user_created", "ad_deliveries", ["user_id", "created_at"])

    op.create_table(
        "ad_events",
        sa.Column("ad_id", sa.Uuid(), nullable=False),
        sa.Column("delivery_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ad_id"], ["ad_placements.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["delivery_id"], ["ad_deliveries.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("delivery_id", "event_type", name="uq_ad_events_delivery_event"),
    )
    for column in ("ad_id", "delivery_id", "user_id", "event_type"):
        op.create_index(f"ix_ad_events_{column}", "ad_events", [column])
    op.create_index("ix_ad_events_ad_created", "ad_events", ["ad_id", "created_at"])

    op.create_table(
        "daily_reward_claims",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("claim_date", sa.Date(), nullable=False),
        sa.Column("streak_day", sa.Integer(), nullable=False),
        sa.Column("coins", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("coins > 0", name="ck_daily_reward_claims_daily_reward_coins_positive"),
        sa.ForeignKeyConstraint(["ledger_id"], ["wallet_ledger.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ledger_id", name="uq_daily_reward_claims_ledger_id"),
        sa.UniqueConstraint("user_id", "claim_date", name="uq_daily_reward_user_date"),
    )
    op.create_index("ix_daily_reward_claims_user_id", "daily_reward_claims", ["user_id"])
    op.create_index("ix_daily_reward_claims_claim_date", "daily_reward_claims", ["claim_date"])

    op.create_table(
        "referral_codes",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_referral_codes_code"),
        sa.UniqueConstraint("user_id", name="uq_referral_codes_user_id"),
    )
    op.create_index("ix_referral_codes_user_id", "referral_codes", ["user_id"])
    op.create_index("ix_referral_codes_code", "referral_codes", ["code"])

    op.create_table(
        "referrals",
        sa.Column("inviter_id", sa.Uuid(), nullable=False),
        sa.Column("invitee_id", sa.Uuid(), nullable=False),
        sa.Column("code_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="qualified", nullable=False),
        sa.Column("inviter_reward", sa.Integer(), server_default="50", nullable=False),
        sa.Column("invitee_reward", sa.Integer(), server_default="25", nullable=False),
        sa.Column("qualified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("invitee_reward >= 0", name="ck_referrals_invitee_reward_non_negative"),
        sa.CheckConstraint("inviter_reward >= 0", name="ck_referrals_inviter_reward_non_negative"),
        sa.ForeignKeyConstraint(["code_id"], ["referral_codes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["invitee_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invitee_id", name="uq_referrals_invitee"),
    )
    for column in ("inviter_id", "invitee_id", "code_id"):
        op.create_index(f"ix_referrals_{column}", "referrals", [column])

    op.create_table(
        "social_identities",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "subject", name="uq_social_identity_provider_subject"),
        sa.UniqueConstraint("user_id", "provider", name="uq_social_identity_user_provider"),
    )
    for column in ("user_id", "provider", "subject", "email"):
        op.create_index(f"ix_social_identities_{column}", "social_identities", [column])

    op.create_table(
        "watch_parties",
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("content_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=True),
        sa.Column("invite_code", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="lobby", nullable=False),
        sa.Column("position_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("paused", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("max_members", sa.Integer(), server_default="10", nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "max_members >= 2 AND max_members <= 25",
            name="ck_watch_parties_max_members_range",
        ),
        sa.CheckConstraint(
            "position_seconds >= 0",
            name="ck_watch_parties_watch_party_position_non_negative",
        ),
        sa.ForeignKeyConstraint(["content_id"], ["content.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["host_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invite_code", name="uq_watch_parties_invite_code"),
    )
    for column in (
        "host_id",
        "content_id",
        "episode_id",
        "invite_code",
        "last_heartbeat_at",
    ):
        op.create_index(f"ix_watch_parties_{column}", "watch_parties", [column])
    op.create_index("ix_watch_parties_host_status", "watch_parties", ["host_id", "status"])

    op.create_table(
        "watch_party_members",
        sa.Column("party_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=True),
        sa.Column("role", sa.String(length=20), server_default="guest", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["party_id"], ["watch_parties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["viewer_profiles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("party_id", "user_id", name="uq_watch_party_member_user"),
    )
    for column in ("party_id", "user_id", "profile_id", "last_seen_at"):
        op.create_index(f"ix_watch_party_members_{column}", "watch_party_members", [column])
    op.create_index(
        "ix_watch_party_members_party_status", "watch_party_members", ["party_id", "status"]
    )

    op.create_table(
        "watch_party_messages",
        sa.Column("party_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["party_id"], ["watch_parties.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_watch_party_messages_party_id", "watch_party_messages", ["party_id"])
    op.create_index("ix_watch_party_messages_user_id", "watch_party_messages", ["user_id"])
    op.create_index(
        "ix_watch_party_messages_party_created",
        "watch_party_messages",
        ["party_id", "created_at"],
    )

    op.create_table(
        "growth_automations",
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("trigger_event", sa.String(length=80), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("action_config", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("cooldown_hours", sa.Integer(), server_default="24", nullable=False),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key", name="uq_growth_automations_key"),
    )
    for column in ("key", "trigger_event", "active"):
        op.create_index(f"ix_growth_automations_{column}", "growth_automations", [column])

    op.create_table(
        "growth_events",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("event_name", sa.String(length=80), nullable=False),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_growth_events_user_id", "growth_events", ["user_id"])
    op.create_index("ix_growth_events_event_name", "growth_events", ["event_name"])
    op.create_index("ix_growth_events_name_created", "growth_events", ["event_name", "created_at"])

    now = datetime.now(UTC)
    ads = sa.table(
        "ad_placements",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("placement", sa.String()),
        sa.column("format", sa.String()),
        sa.column("headline", sa.String()),
        sa.column("body", sa.Text()),
        sa.column("click_url", sa.String()),
        sa.column("sponsor", sa.String()),
        sa.column("countries", sa.JSON()),
        sa.column("languages", sa.JSON()),
        sa.column("reward_coins", sa.Integer()),
        sa.column("daily_cap", sa.Integer()),
        sa.column("priority", sa.Integer()),
        sa.column("active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        ads,
        [
            {
                "id": uuid4(),
                "key": "drovixa-premium-house",
                "name": "Drovixa Premium house ad",
                "placement": "home_feed",
                "format": "card",
                "headline": "Watch without limits",
                "body": "Unlock premium stories, downloads and the full Drovixa experience.",
                "click_url": "/premium",
                "sponsor": "Drovixa",
                "countries": [],
                "languages": [],
                "reward_coins": 0,
                "daily_cap": 2,
                "priority": 100,
                "active": True,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    automations = sa.table(
        "growth_automations",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("name", sa.String()),
        sa.column("trigger_event", sa.String()),
        sa.column("action_type", sa.String()),
        sa.column("action_config", sa.JSON()),
        sa.column("cooldown_hours", sa.Integer()),
        sa.column("active", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        automations,
        [
            {
                "id": uuid4(),
                "key": "daily-reward-return",
                "name": "Daily reward follow-up",
                "trigger_event": "daily_reward_claimed",
                "action_type": "notification",
                "action_config": {
                    "title": "Your streak is alive",
                    "body": "Come back tomorrow for the next Drovixa coin reward.",
                    "action_url": "/rewards",
                },
                "cooldown_hours": 20,
                "active": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": uuid4(),
                "key": "referral-welcome",
                "name": "Referral reward welcome",
                "trigger_event": "referral_qualified",
                "action_type": "notification",
                "action_config": {
                    "title": "Referral reward unlocked",
                    "body": "Your bonus coins are ready in your Drovixa wallet.",
                    "action_url": "/coins",
                },
                "cooldown_hours": 0,
                "active": True,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    op.execute(
        sa.text(
            "UPDATE feature_flags SET enabled = true, rollout_percentage = 100 "
            "WHERE key IN ('ads_enabled','daily_rewards_enabled','referrals_enabled',"
            "'social_login_enabled','watch_party_enabled')"
        )
    )


def downgrade() -> None:
    op.drop_table("growth_events")
    op.drop_table("growth_automations")
    op.drop_table("watch_party_messages")
    op.drop_table("watch_party_members")
    op.drop_table("watch_parties")
    op.drop_table("social_identities")
    op.drop_table("referrals")
    op.drop_table("referral_codes")
    op.drop_table("daily_reward_claims")
    op.drop_table("ad_events")
    op.drop_table("ad_deliveries")
    op.drop_table("ad_placements")
