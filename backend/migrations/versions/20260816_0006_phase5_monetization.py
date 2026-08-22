"""phase 5 monetization

Revision ID: 20260816_0006
Revises: 20260814_0005
Create Date: 2026-08-16 02:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260816_0006"
down_revision: str | None = "20260814_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


wallet_type = sa.Enum(
    "purchase",
    "bonus",
    "episode_unlock",
    "refund",
    "promotion",
    "daily_reward",
    "referral",
    "admin_adjustment",
    "expiration",
    name="wallet_transaction_type",
)
ledger_status = sa.Enum("pending", "completed", "reversed", "failed", name="ledger_status")
package_platform = sa.Enum("web", "android", "ios", name="coin_package_platform")
subscription_interval = sa.Enum(
    "monthly", "quarterly", "annual", name="subscription_interval"
)
subscription_status = sa.Enum(
    "trialing",
    "active",
    "past_due",
    "cancelled",
    "expired",
    "refunded",
    name="subscription_status",
)
payment_product_type = sa.Enum("coins", "subscription", name="payment_product_type")
payment_status = sa.Enum(
    "pending",
    "processing",
    "paid",
    "failed",
    "cancelled",
    "refunded",
    "partially_refunded",
    name="payment_status",
)
payment_platform = sa.Enum("web", "android", "ios", name="payment_platform")
payment_event_status = sa.Enum(
    "pending", "completed", "reversed", "failed", name="payment_event_status"
)
refund_status = sa.Enum(
    "pending", "processing", "succeeded", "failed", name="refund_status"
)


def upgrade() -> None:
    op.create_table(
        "wallets",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("coin_balance", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bonus_coin_balance", sa.Integer(), server_default="0", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "coin_balance >= 0", name=op.f("ck_wallets_coin_balance_non_negative")
        ),
        sa.CheckConstraint(
            "bonus_coin_balance >= 0", name=op.f("ck_wallets_bonus_balance_non_negative")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", name="pk_wallets"),
    )
    op.execute(
        sa.text(
            "INSERT INTO wallets (user_id, coin_balance, bonus_coin_balance, created_at, updated_at) "
            "SELECT id, 0, 0, now(), now() FROM users"
        )
    )

    op.create_table(
        "coin_packages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("coins", sa.Integer(), nullable=False),
        sa.Column("bonus_coins", sa.Integer(), server_default="0", nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("platform", package_platform, server_default="web", nullable=False),
        sa.Column("store_product_id", sa.String(255), nullable=True),
        sa.Column("country_id", sa.Uuid(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("featured", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("coins > 0", name=op.f("ck_coin_packages_coins_positive")),
        sa.CheckConstraint(
            "bonus_coins >= 0", name=op.f("ck_coin_packages_bonus_coins_non_negative")
        ),
        sa.CheckConstraint("price > 0", name=op.f("ck_coin_packages_price_positive")),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_coin_packages"),
        sa.UniqueConstraint(
            "platform", "store_product_id", name="uq_coin_package_store_product"
        ),
    )
    op.create_index("ix_coin_packages_platform", "coin_packages", ["platform"])
    op.create_index("ix_coin_packages_country_id", "coin_packages", ["country_id"])
    op.create_index("ix_coin_packages_active", "coin_packages", ["active"])

    op.create_table(
        "subscription_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False),
        sa.Column("interval", subscription_interval, nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("featured", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("trial_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provider_price_id", sa.String(255), nullable=True),
        sa.Column("store_product_ids", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("benefits", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("price > 0", name=op.f("ck_subscription_plans_price_positive")),
        sa.CheckConstraint(
            "trial_days >= 0", name=op.f("ck_subscription_plans_trial_days_non_negative")
        ),
        sa.PrimaryKeyConstraint("id", name="pk_subscription_plans"),
    )
    op.create_index("ix_subscription_plans_slug", "subscription_plans", ["slug"], unique=True)
    op.create_index("ix_subscription_plans_active", "subscription_plans", ["active"])
    op.create_index(
        "ix_subscription_plans_provider_price_id", "subscription_plans", ["provider_price_id"]
    )

    op.create_table(
        "wallet_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", wallet_type, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("balance_before", sa.Integer(), nullable=False),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("coin_balance_before", sa.Integer(), nullable=False),
        sa.Column("coin_balance_after", sa.Integer(), nullable=False),
        sa.Column("bonus_balance_before", sa.Integer(), nullable=False),
        sa.Column("bonus_balance_after", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("status", ledger_status, server_default="completed", nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "balance_before >= 0", name=op.f("ck_wallet_ledger_balance_before_non_negative")
        ),
        sa.CheckConstraint(
            "balance_after >= 0", name=op.f("ck_wallet_ledger_balance_after_non_negative")
        ),
        sa.CheckConstraint(
            "coin_balance_before >= 0", name=op.f("ck_wallet_ledger_coin_before_non_negative")
        ),
        sa.CheckConstraint(
            "coin_balance_after >= 0", name=op.f("ck_wallet_ledger_coin_after_non_negative")
        ),
        sa.CheckConstraint(
            "bonus_balance_before >= 0", name=op.f("ck_wallet_ledger_bonus_before_non_negative")
        ),
        sa.CheckConstraint(
            "bonus_balance_after >= 0", name=op.f("ck_wallet_ledger_bonus_after_non_negative")
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_wallet_ledger"),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_wallet_ledger_idempotency"
        ),
    )
    op.create_index("ix_wallet_ledger_user_id", "wallet_ledger", ["user_id"])
    op.create_index("ix_wallet_ledger_type", "wallet_ledger", ["type"])
    op.create_index("ix_wallet_ledger_reference", "wallet_ledger", ["reference"])
    op.create_index("ix_wallet_ledger_status", "wallet_ledger", ["status"])
    op.create_index(
        "ix_wallet_ledger_user_created", "wallet_ledger", ["user_id", "created_at"]
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("provider_transaction_id", sa.String(255), nullable=True),
        sa.Column("product_type", payment_product_type, nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", payment_status, server_default="pending", nullable=False),
        sa.Column("platform", payment_platform, nullable=False),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        *timestamps(),
        sa.CheckConstraint("amount > 0", name=op.f("ck_payments_amount_positive")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
        sa.UniqueConstraint(
            "user_id", "idempotency_key", name="uq_payment_user_idempotency"
        ),
        sa.UniqueConstraint(
            "provider", "provider_transaction_id", name="uq_payment_provider_transaction"
        ),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_provider", "payments", ["provider"])
    op.create_index("ix_payments_product_type", "payments", ["product_type"])
    op.create_index("ix_payments_product_id", "payments", ["product_id"])
    op.create_index("ix_payments_status", "payments", ["status"])
    op.create_index("ix_payments_platform", "payments", ["platform"])
    op.create_index("ix_payments_user_created", "payments", ["user_id", "created_at"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("provider_subscription_id", sa.String(255), nullable=True),
        sa.Column("status", subscription_status, server_default="active", nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_subscriptions"),
        sa.UniqueConstraint(
            "provider", "provider_subscription_id", name="uq_subscription_provider_reference"
        ),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"])
    op.create_index("ix_subscriptions_plan_id", "subscriptions", ["plan_id"])
    op.create_index("ix_subscriptions_provider", "subscriptions", ["provider"])
    op.create_index("ix_subscriptions_status", "subscriptions", ["status"])
    op.create_index(
        "ix_subscriptions_current_period_end", "subscriptions", ["current_period_end"]
    )
    op.create_index("ix_subscriptions_ended_at", "subscriptions", ["ended_at"])
    op.create_index(
        "ix_subscriptions_user_status", "subscriptions", ["user_id", "status"]
    )

    op.create_table(
        "episode_unlocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("ledger_transaction_id", sa.Uuid(), nullable=False),
        sa.Column("coin_price", sa.Integer(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["episode_id"], ["episodes.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["ledger_transaction_id"], ["wallet_ledger.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_episode_unlocks"),
        sa.UniqueConstraint(
            "user_id", "episode_id", name="uq_episode_unlock_user_episode"
        ),
        sa.UniqueConstraint("ledger_transaction_id"),
    )
    op.create_index("ix_episode_unlocks_user_id", "episode_unlocks", ["user_id"])
    op.create_index("ix_episode_unlocks_episode_id", "episode_unlocks", ["episode_id"])
    op.create_index(
        "ix_episode_unlocks_user_created", "episode_unlocks", ["user_id", "created_at"]
    )

    op.create_table(
        "payment_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(80), nullable=False),
        sa.Column("provider_event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("status", payment_event_status, server_default="pending", nullable=False),
        sa.Column("payload", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("raw_reference", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_payment_events"),
    )
    op.create_index("ix_payment_events_provider", "payment_events", ["provider"])
    op.create_index(
        "ix_payment_events_provider_event_id",
        "payment_events",
        ["provider_event_id"],
        unique=True,
    )
    op.create_index("ix_payment_events_event_type", "payment_events", ["event_type"])
    op.create_index("ix_payment_events_payment_id", "payment_events", ["payment_id"])
    op.create_index("ix_payment_events_status", "payment_events", ["status"])

    op.create_table(
        "refunds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("provider_refund_id", sa.String(255), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", refund_status, server_default="pending", nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("metadata", sa.JSON(), server_default="{}", nullable=False),
        *timestamps(),
        sa.CheckConstraint("amount > 0", name=op.f("ck_refunds_amount_positive")),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_refunds"),
        sa.UniqueConstraint("provider_refund_id"),
    )
    op.create_index("ix_refunds_payment_id", "refunds", ["payment_id"])
    op.create_index("ix_refunds_status", "refunds", ["status"])


def downgrade() -> None:
    op.drop_table("refunds")
    op.drop_table("payment_events")
    op.drop_table("episode_unlocks")
    op.drop_table("subscriptions")
    op.drop_table("payments")
    op.drop_table("wallet_ledger")
    op.drop_table("subscription_plans")
    op.drop_table("coin_packages")
    op.drop_table("wallets")

    bind = op.get_bind()
    for enum_type in (
        refund_status,
        payment_event_status,
        payment_platform,
        payment_status,
        payment_product_type,
        subscription_status,
        subscription_interval,
        package_platform,
        ledger_status,
        wallet_type,
    ):
        enum_type.drop(bind, checkfirst=True)
