from functools import lru_cache

from app.core.config import get_settings
from app.integrations.payments.base import PaymentProvider
from app.integrations.payments.disabled import DisabledPaymentProvider
from app.integrations.payments.stripe import StripePaymentProvider


@lru_cache
def get_payment_provider() -> PaymentProvider:
    settings = get_settings()
    if settings.PAYMENT_PROVIDER == "stripe":
        return StripePaymentProvider(settings)
    return DisabledPaymentProvider()
