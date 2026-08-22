from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class CheckoutRequest:
    payment_id: str
    idempotency_key: str
    product_name: str
    product_type: str
    currency: str
    amount: Decimal
    quantity: int
    customer_email: str
    success_url: str
    cancel_url: str
    provider_price_id: str | None = None
    subscription: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    provider_transaction_id: str
    checkout_url: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProviderEvent:
    event_id: str
    event_type: str
    provider_transaction_id: str | None
    payment_id: str | None
    status: str | None
    subscription_id: str | None = None
    period_end: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RefundResult:
    provider_refund_id: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict)


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    async def create_checkout(self, request: CheckoutRequest) -> CheckoutResult:
        """Create a hosted checkout using a backend-authoritative amount."""

    @abstractmethod
    async def verify_payment(self, provider_transaction_id: str) -> str:
        """Return the normalized provider payment status."""

    @abstractmethod
    async def refund_payment(
        self, provider_transaction_id: str, *, amount: Decimal | None = None
    ) -> RefundResult:
        """Refund a paid provider transaction."""

    @abstractmethod
    def handle_webhook(self, *, body: bytes, signature: str | None) -> ProviderEvent:
        """Verify a provider signature and normalize one webhook event."""

    @abstractmethod
    async def get_payment_status(self, provider_transaction_id: str) -> str:
        """Fetch the normalized status from the provider."""

    async def cancel_subscription(self, provider_subscription_id: str) -> None:
        del provider_subscription_id
