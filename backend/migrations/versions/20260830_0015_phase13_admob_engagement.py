"""phase 13 AdMob rewards and engagement automation

Revision ID: 20260830_0015
Revises: 20260829_0014
Create Date: 2026-08-30 12:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0015"
down_revision: str | None = "20260829_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FLAG_KEYS = (
    "rewarded_ads_enabled",
    "premium_offers_enabled",
    "content_notifications_enabled",
    "continue_watching_reminders_enabled",
)
CONFIG_KEYS = ("admob_rewarded", "premium_engagement")
AUTOMATION_KEYS = ("premium-offer-notification", "continue-watching-reminder")


def upgrade() -> None:
    op.create_table(
        "rewarded_ad_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("session_token", sa.String(length=96), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("ad_unit_id", sa.String(length=160), nullable=False),
        sa.Column("reward_coins", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("admob_transaction_id", sa.String(length=200), nullable=True),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_metadata", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "reward_coins > 0",
            name="ck_rewarded_ad_sessions_rewarded_ad_coins_positive",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token", name="uq_rewarded_ad_session_token"),
        sa.UniqueConstraint("admob_transaction_id", name="uq_rewarded_ad_transaction"),
    )
    op.create_index("ix_rewarded_ad_sessions_user_id", "rewarded_ad_sessions", ["user_id"])
    op.create_index("ix_rewarded_ad_sessions_expires_at", "rewarded_ad_sessions", ["expires_at"])
    op.create_index("ix_rewarded_ad_sessions_credited_at", "rewarded_ad_sessions", ["credited_at"])
    op.create_index(
        "ix_rewarded_ad_user_created", "rewarded_ad_sessions", ["user_id", "created_at"]
    )
    op.create_index(
        "ix_rewarded_ad_status_expires", "rewarded_ad_sessions", ["status", "expires_at"]
    )

    now = datetime.now(UTC)
    flags = sa.table(
        "feature_flags",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("enabled", sa.Boolean()),
        sa.column("rollout_percentage", sa.Integer()),
        sa.column("rules", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        flags,
        [
            {
                "id": uuid4(),
                "key": key,
                "description": description,
                "enabled": True,
                "rollout_percentage": 100,
                "rules": {},
                "created_at": now,
                "updated_at": now,
            }
            for key, description in (
                ("rewarded_ads_enabled", "Google AdMob rewarded ads for non-Premium viewers."),
                ("premium_offers_enabled", "Respectfully timed Premium offers in the mobile app."),
                (
                    "content_notifications_enabled",
                    "Automatic notifications for newly published content.",
                ),
                (
                    "continue_watching_reminders_enabled",
                    "Automatic reminders for unfinished videos.",
                ),
            )
        ],
    )

    configs = sa.table(
        "remote_config",
        sa.column("id", sa.Uuid()),
        sa.column("key", sa.String()),
        sa.column("value", sa.JSON()),
        sa.column("description", sa.Text()),
        sa.column("is_public", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        configs,
        [
            {
                "id": uuid4(),
                "key": "admob_rewarded",
                "value": {"coins_per_ad": 10, "daily_limit": 5},
                "description": "Server-enforced AdMob reward and daily cap.",
                "is_public": False,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": uuid4(),
                "key": "premium_engagement",
                "value": {
                    "max_per_session": 2,
                    "max_per_day": 3,
                    "first_delay_seconds": 90,
                    "repeat_delay_seconds": 480,
                    "notification_cooldown_hours": 72,
                    "continue_after_hours": 24,
                    "continue_cooldown_hours": 48,
                },
                "description": "Frequency limits for Premium offers and viewing reminders.",
                "is_public": False,
                "created_at": now,
                "updated_at": now,
            },
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
                "key": "premium-offer-notification",
                "name": "Premium offer notification",
                "trigger_event": "scheduled",
                "action_type": "notification",
                "action_config": {"action_url": "/premium", "segment": "non_premium"},
                "cooldown_hours": 72,
                "active": True,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": uuid4(),
                "key": "continue-watching-reminder",
                "name": "Continue watching reminder",
                "trigger_event": "scheduled",
                "action_type": "notification",
                "action_config": {"segment": "unfinished_viewers"},
                "cooldown_hours": 6,
                "active": True,
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    automations = sa.table("growth_automations", sa.column("key", sa.String()))
    configs = sa.table("remote_config", sa.column("key", sa.String()))
    flags = sa.table("feature_flags", sa.column("key", sa.String()))
    op.execute(automations.delete().where(automations.c.key.in_(AUTOMATION_KEYS)))
    op.execute(configs.delete().where(configs.c.key.in_(CONFIG_KEYS)))
    op.execute(flags.delete().where(flags.c.key.in_(FLAG_KEYS)))
    op.drop_index("ix_rewarded_ad_status_expires", table_name="rewarded_ad_sessions")
    op.drop_index("ix_rewarded_ad_user_created", table_name="rewarded_ad_sessions")
    op.drop_index("ix_rewarded_ad_sessions_credited_at", table_name="rewarded_ad_sessions")
    op.drop_index("ix_rewarded_ad_sessions_expires_at", table_name="rewarded_ad_sessions")
    op.drop_index("ix_rewarded_ad_sessions_user_id", table_name="rewarded_ad_sessions")
    op.drop_table("rewarded_ad_sessions")
