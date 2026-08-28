from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.models.enums import PaymentPlatform, SubscriptionInterval


class CheckoutInput(BaseModel):
    product_id: UUID
    success_url: HttpUrl | None = None
    cancel_url: HttpUrl | None = None
    country: str | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class MobilePurchaseVerifyInput(BaseModel):
    platform: PaymentPlatform
    product_type: str = Field(pattern="^(coins|subscription)$")
    product_id: UUID
    store_product_id: str = Field(min_length=2, max_length=255)
    transaction_id: str = Field(min_length=2, max_length=255)
    receipt: str = Field(min_length=8, max_length=2_000_000)

    @field_validator("platform")
    @classmethod
    def native_platform_only(cls, value: PaymentPlatform) -> PaymentPlatform:
        if value == PaymentPlatform.WEB:
            raise ValueError("Mobile purchase platform must be android or ios")
        return value


class CoinPackageCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    coins: int = Field(gt=0, le=10_000_000)
    bonus_coins: int = Field(default=0, ge=0, le=10_000_000)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", pattern="^[A-Za-z]{3}$")
    platform: PaymentPlatform = PaymentPlatform.WEB
    store_product_id: str | None = Field(default=None, max_length=255)
    country_id: UUID | None = None
    active: bool = True
    featured: bool = False
    sort_order: int = Field(default=0, ge=0)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class CoinPackageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    coins: int | None = Field(default=None, gt=0, le=10_000_000)
    bonus_coins: int | None = Field(default=None, ge=0, le=10_000_000)
    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, pattern="^[A-Za-z]{3}$")
    platform: PaymentPlatform | None = None
    store_product_id: str | None = Field(default=None, max_length=255)
    country_id: UUID | None = None
    active: bool | None = None
    featured: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class SubscriptionPlanCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=140)
    interval: SubscriptionInterval
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="USD", pattern="^[A-Za-z]{3}$")
    active: bool = True
    featured: bool = False
    trial_days: int = Field(default=0, ge=0, le=365)
    provider_price_id: str | None = Field(default=None, max_length=255)
    store_product_ids: dict[str, str] = Field(default_factory=dict)
    benefits: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = Field(default=0, ge=0)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()


class SubscriptionPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    slug: str | None = Field(default=None, pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=140)
    interval: SubscriptionInterval | None = None
    price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, pattern="^[A-Za-z]{3}$")
    active: bool | None = None
    featured: bool | None = None
    trial_days: int | None = Field(default=None, ge=0, le=365)
    provider_price_id: str | None = Field(default=None, max_length=255)
    store_product_ids: dict[str, str] | None = None
    benefits: dict[str, Any] | None = None
    sort_order: int | None = Field(default=None, ge=0)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class WalletAdjustmentInput(BaseModel):
    amount: int = Field(ge=-10_000_000, le=10_000_000)
    bonus_amount: int = Field(default=0, ge=-10_000_000, le=10_000_000)
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("bonus_amount")
    @classmethod
    def at_least_one_change(cls, value: int, info: Any) -> int:
        amount = info.data.get("amount", 0)
        if amount == 0 and value == 0:
            raise ValueError("An adjustment amount is required")
        return value


class AdminSubscriptionGrantInput(BaseModel):
    plan_id: UUID | None = None
    days: int = Field(default=30, ge=1, le=36500)
    reason: str = Field(min_length=3, max_length=500)


class AdminSubscriptionRevokeInput(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class SubscriptionCancelInput(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class RefundInput(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    reason: str | None = Field(default=None, max_length=500)
