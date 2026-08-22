"""phase 9 Firebase push notifications

Revision ID: 20260823_0010
Revises: 20260822_0009
Create Date: 2026-08-23 00:10:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260823_0010"
down_revision: str | None = "20260822_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "push_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column("locale", sa.String(length=20), nullable=True),
        sa.Column("last_registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_push_tokens_token_hash"),
        sa.UniqueConstraint(
            "user_id", "device_id", "provider", name="uq_push_tokens_user_device_provider"
        ),
    )
    op.create_index("ix_push_tokens_user_id", "push_tokens", ["user_id"], unique=False)
    op.create_index("ix_push_tokens_token_hash", "push_tokens", ["token_hash"], unique=True)
    op.create_index(
        "ix_push_tokens_active_provider", "push_tokens", ["active", "provider"], unique=False
    )

    op.create_table(
        "notification_deliveries",
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("push_token_id", sa.Uuid(), nullable=True),
        sa.Column("channel", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("provider_message_id", sa.String(length=512), nullable=True),
        sa.Column("error_code", sa.String(length=160), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"], ["notification_campaigns.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["push_token_id"], ["push_tokens.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_id",
            "push_token_id",
            "channel",
            name="uq_notification_deliveries_campaign_token_channel",
        ),
    )
    op.create_index(
        "ix_notification_deliveries_campaign_id",
        "notification_deliveries",
        ["campaign_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_user_id",
        "notification_deliveries",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_push_token_id",
        "notification_deliveries",
        ["push_token_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_deliveries_campaign_status",
        "notification_deliveries",
        ["campaign_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_deliveries_campaign_status", table_name="notification_deliveries"
    )
    op.drop_index(
        "ix_notification_deliveries_push_token_id", table_name="notification_deliveries"
    )
    op.drop_index("ix_notification_deliveries_user_id", table_name="notification_deliveries")
    op.drop_index(
        "ix_notification_deliveries_campaign_id", table_name="notification_deliveries"
    )
    op.drop_table("notification_deliveries")
    op.drop_index("ix_push_tokens_active_provider", table_name="push_tokens")
    op.drop_index("ix_push_tokens_token_hash", table_name="push_tokens")
    op.drop_index("ix_push_tokens_user_id", table_name="push_tokens")
    op.drop_table("push_tokens")
