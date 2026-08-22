from __future__ import annotations

from decimal import Decimal

from app.core.exceptions import AppError
from app.integrations.payments.base import (
    CheckoutRequest,
    CheckoutResult,
    PaymentProvider,
    ProviderEvent,
    RefundResult,
)


class DisabledPaymentProvider(PaymentProvider):
    name = "disabled"

    @staticmethod
    def _unavailable() -> AppError:
        return AppError(
            "PAYMENT_PROVIDER_UNAVAILABLE",
            "Online payments are not configured yet.",
            status_code=503,
        )

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutResult:
        del request
        raise self._unavailable()

    async def verify_payment(self, provider_transaction_id: str) -> str:
        del provider_transaction_id
        raise self._unavailable()

    async def refund_payment(
        self, provider_transaction_id: str, *, amount: Decimal | None = None
    ) -> RefundResult:
        del provider_transaction_id, amount
        raise self._unavailable()

    def handle_webhook(self, *, body: bytes, signature: str | None) -> ProviderEvent:
        del body, signature
        raise self._unavailable()

    async def get_payment_status(self, provider_transaction_id: str) -> str:
        del provider_transaction_id
        raise self._unavailable()
