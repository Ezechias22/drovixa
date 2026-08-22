from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.content import enum_values
from app.models.enums import (
    LedgerStatus,
    PaymentPlatform,
    PaymentProductType,
    PaymentStatus,
    RefundStatus,
    SubscriptionInterval,
    SubscriptionStatus,
    WalletTransactionType,
)


class Wallet(TimestampMixin, Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("coin_balance >= 0", name="coin_balance_non_negative"),
        CheckConstraint("bonus_coin_balance >= 0", name="bonus_balance_non_negative"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    coin_balance: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    bonus_coin_balance: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class WalletLedger(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wallet_ledger"
    __table_args__ = (
        CheckConstraint("balance_before >= 0", name="balance_before_non_negative"),
        CheckConstraint("balance_after >= 0", name="balance_after_non_negative"),
        CheckConstraint("coin_balance_before >= 0", name="coin_before_non_negative"),
        CheckConstraint("coin_balance_after >= 0", name="coin_after_non_negative"),
        CheckConstraint("bonus_balance_before >= 0", name="bonus_before_non_negative"),
        CheckConstraint("bonus_balance_after >= 0", name="bonus_after_non_negative"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_wallet_ledger_idempotency"),
        Index("ix_wallet_ledger_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    type: Mapped[WalletTransactionType] = mapped_column(
        Enum(WalletTransactionType, name="wallet_transaction_type", values_callable=enum_values),
        index=True,
    )
    amount: Mapped[int]
    balance_before: Mapped[int]
    balance_after: Mapped[int]
    coin_balance_before: Mapped[int]
    coin_balance_after: Mapped[int]
    bonus_balance_before: Mapped[int]
    bonus_balance_after: Mapped[int]
    reference: Mapped[str | None] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(80))
    status: Mapped[LedgerStatus] = mapped_column(
        Enum(LedgerStatus, name="ledger_status", values_callable=enum_values),
        default=LedgerStatus.COMPLETED,
        server_default=LedgerStatus.COMPLETED.value,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128))
    transaction_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, server_default="{}"
    )


class CoinPackage(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "coin_packages"
    __table_args__ = (
        CheckConstraint("coins > 0", name="coins_positive"),
        CheckConstraint("bonus_coins >= 0", name="bonus_coins_non_negative"),
        CheckConstraint("price > 0", name="price_positive"),
        UniqueConstraint("platform", "store_product_id", name="uq_coin_package_store_product"),
    )

    name: Mapped[str] = mapped_column(String(120))
    coins: Mapped[int]
    bonus_coins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    platform: Mapped[PaymentPlatform] = mapped_column(
        Enum(PaymentPlatform, name="coin_package_platform", values_callable=enum_values),
        default=PaymentPlatform.WEB,
        server_default=PaymentPlatform.WEB.value,
        index=True,
    )
    store_product_id: Mapped[str | None] = mapped_column(String(255))
    country_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("countries.id", ondelete="SET NULL"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class EpisodeUnlock(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "episode_unlocks"
    __table_args__ = (
        UniqueConstraint("user_id", "episode_id", name="uq_episode_unlock_user_episode"),
        Index("ix_episode_unlocks_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    episode_id: Mapped[UUID] = mapped_column(
        ForeignKey("episodes.id", ondelete="RESTRICT"), index=True
    )
    ledger_transaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("wallet_ledger.id", ondelete="RESTRICT"), unique=True
    )
    coin_price: Mapped[int]


class SubscriptionPlan(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "subscription_plans"
    __table_args__ = (
        CheckConstraint("price > 0", name="price_positive"),
        CheckConstraint("trial_days >= 0", name="trial_days_non_negative"),
    )

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    interval: Mapped[SubscriptionInterval] = mapped_column(
        Enum(SubscriptionInterval, name="subscription_interval", values_callable=enum_values)
    )
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", index=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    trial_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    provider_price_id: Mapped[str | None] = mapped_column(String(255), index=True)
    store_product_ids: Mapped[dict[str, str]] = mapped_column(
        JSON, default=dict, server_default="{}"
    )
    benefits: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index("ix_subscriptions_user_status", "user_id", "status"),
        UniqueConstraint(
            "provider", "provider_subscription_id", name="uq_subscription_provider_reference"
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[str] = mapped_column(String(80), index=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status", values_callable=enum_values),
        default=SubscriptionStatus.ACTIVE,
        server_default=SubscriptionStatus.ACTIVE.value,
        index=True,
    )
    starts_at: Mapped[datetime]
    current_period_start: Mapped[datetime]
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    subscription_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, server_default="{}"
    )

    plan: Mapped[SubscriptionPlan] = relationship(lazy="joined")


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_payment_user_idempotency"),
        UniqueConstraint(
            "provider", "provider_transaction_id", name="uq_payment_provider_transaction"
        ),
        CheckConstraint("amount > 0", name="amount_positive"),
        Index("ix_payments_user_created", "user_id", "created_at"),
        Index("ix_payments_status_created", "status", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    provider_transaction_id: Mapped[str | None] = mapped_column(String(255))
    product_type: Mapped[PaymentProductType] = mapped_column(
        Enum(PaymentProductType, name="payment_product_type", values_callable=enum_values),
        index=True,
    )
    product_id: Mapped[UUID] = mapped_column(index=True)
    currency: Mapped[str] = mapped_column(String(3))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status", values_callable=enum_values),
        default=PaymentStatus.PENDING,
        server_default=PaymentStatus.PENDING.value,
        index=True,
    )
    platform: Mapped[PaymentPlatform] = mapped_column(
        Enum(PaymentPlatform, name="payment_platform", values_callable=enum_values), index=True
    )
    country: Mapped[str | None] = mapped_column(String(2))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    payment_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, server_default="{}"
    )


class PaymentEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payment_events"

    provider: Mapped[str] = mapped_column(String(80), index=True)
    provider_event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    payment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[LedgerStatus] = mapped_column(
        Enum(LedgerStatus, name="payment_event_status", values_callable=enum_values),
        default=LedgerStatus.PENDING,
        server_default=LedgerStatus.PENDING.value,
        index=True,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    raw_reference: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    error_message: Mapped[str | None] = mapped_column(String(1000))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Refund(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "refunds"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), index=True
    )
    provider_refund_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status", values_callable=enum_values),
        default=RefundStatus.PENDING,
        server_default=RefundStatus.PENDING.value,
        index=True,
    )
    reason: Mapped[str | None] = mapped_column(String(500))
    refund_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, server_default="{}"
    )
