from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.exceptions import AppError


@dataclass(frozen=True, slots=True)
class VerifiedMobilePurchase:
    transaction_id: str
    product_id: str
    platform: str
    active: bool
    raw_reference: dict[str, Any] = field(default_factory=dict)


class MobileReceiptVerifier(ABC):
    @abstractmethod
    async def verify(
        self, *, platform: str, product_id: str, transaction_id: str, receipt: str
    ) -> VerifiedMobilePurchase:
        """Validate a receipt against Apple or Google servers."""


class UnconfiguredMobileReceiptVerifier(MobileReceiptVerifier):
    async def verify(
        self, *, platform: str, product_id: str, transaction_id: str, receipt: str
    ) -> VerifiedMobilePurchase:
        del platform, product_id, transaction_id, receipt
        raise AppError(
            "IAP_VERIFICATION_NOT_CONFIGURED",
            "Mobile purchase verification is not configured.",
            status_code=503,
        )


def get_mobile_receipt_verifier() -> MobileReceiptVerifier:
    # Real Apple and Google adapters are intentionally activated only when their
    # server credentials and store applications are provisioned. No frontend
    # receipt can grant coins or premium access without this verifier.
    return UnconfiguredMobileReceiptVerifier()
