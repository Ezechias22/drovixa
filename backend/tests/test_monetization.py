from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.payments.base import (
    CheckoutRequest,
    CheckoutResult,
    PaymentProvider,
    ProviderEvent,
    RefundResult,
)
from app.integrations.payments.factory import get_payment_provider
from app.main import app
from app.models.base import utcnow
from app.models.configuration import FeatureFlag
from app.models.content import Content, Episode, Series
from app.models.enums import (
    ContentStatus,
    ContentType,
    ContentVisibility,
    EpisodeAccessType,
    Orientation,
    PaymentPlatform,
    SeriesStatus,
    SubscriptionInterval,
    SubscriptionStatus,
)
from app.models.monetization import (
    CoinPackage,
    EpisodeUnlock,
    Payment,
    PaymentEvent,
    Subscription,
    SubscriptionPlan,
    WalletLedger,
)
from app.models.streaming import UserEntitlement
from app.services.monetization import process_payment_webhook


class FakePaymentProvider(PaymentProvider):
    name = "stripe"

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutResult:
        return CheckoutResult(
            provider_transaction_id=f"checkout_{request.payment_id}",
            checkout_url=f"https://checkout.example.test/{request.payment_id}",
            status="open",
        )

    async def verify_payment(self, provider_transaction_id: str) -> str:
        del provider_transaction_id
        return "paid"

    async def refund_payment(
        self, provider_transaction_id: str, *, amount: Decimal | None = None
    ) -> RefundResult:
        del provider_transaction_id, amount
        return RefundResult("refund_test", "succeeded")

    def handle_webhook(self, *, body: bytes, signature: str | None) -> ProviderEvent:
        del body, signature
        raise AssertionError("not used")

    async def get_payment_status(self, provider_transaction_id: str) -> str:
        del provider_transaction_id
        return "paid"


@pytest.fixture
def fake_payment_provider() -> FakePaymentProvider:
    provider = FakePaymentProvider()
    app.dependency_overrides[get_payment_provider] = lambda: provider
    return provider


@pytest.fixture(autouse=True)
def clear_payment_override() -> Any:
    yield
    app.dependency_overrides.pop(get_payment_provider, None)


async def enable_flag(db: AsyncSession, key: str) -> None:
    row = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
    if row is None:
        db.add(
            FeatureFlag(
                key=key,
                description=key,
                enabled=True,
                rollout_percentage=100,
                rules={},
            )
        )
    else:
        row.enabled = True
    await db.commit()


async def paid_episode(db: AsyncSession, *, price: int = 25) -> Episode:
    content = Content(
        type=ContentType.SERIES,
        title="The Ledger Promise",
        slug=f"ledger-promise-{uuid4().hex[:8]}",
        status=ContentStatus.PUBLISHED,
        visibility=ContentVisibility.PUBLIC,
        published_at=utcnow(),
        allowed_countries=[],
        blocked_countries=[],
    )
    series = Series(
        content=content,
        series_status=SeriesStatus.ONGOING,
        orientation=Orientation.VERTICAL,
    )
    episode = Episode(
        series=series,
        episode_number=1,
        title="The Price of Truth",
        access_type=EpisodeAccessType.COIN_UNLOCK,
        coin_price=price,
        orientation=Orientation.VERTICAL,
        status=ContentStatus.PUBLISHED,
        published_at=utcnow(),
    )
    db.add_all([content, series, episode])
    await db.commit()
    return episode


async def test_wallet_adjustment_and_transactional_episode_unlock(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    admin_headers: dict[str, str],
) -> None:
    await enable_flag(db, "coins_enabled")
    episode = await paid_episode(db)
    user_id = UUID(str(registered["user"]["id"]))
    adjustment = await client.post(
        f"/api/v1/admin/wallets/{user_id}/adjust",
        headers={**admin_headers, "Idempotency-Key": "admin-credit-001"},
        json={"amount": 20, "bonus_amount": 10, "reason": "Phase 5 verification"},
    )
    assert adjustment.status_code == 200, adjustment.text
    assert adjustment.json()["data"]["wallet"]["total_balance"] == 30

    headers = {
        "Authorization": f"Bearer {registered['access_token']}",
        "Idempotency-Key": "unlock-episode-001",
    }
    unlocked = await client.post(f"/api/v1/episodes/{episode.id}/unlock", headers=headers)
    assert unlocked.status_code == 200, unlocked.text
    assert unlocked.json()["data"]["wallet"]["total_balance"] == 5
    assert unlocked.json()["data"]["wallet"]["bonus_coin_balance"] == 0

    repeated = await client.post(f"/api/v1/episodes/{episode.id}/unlock", headers=headers)
    assert repeated.status_code == 200
    assert repeated.json()["data"]["wallet"]["total_balance"] == 5
    assert int(await db.scalar(select(func.count()).select_from(EpisodeUnlock)) or 0) == 1
    assert int(await db.scalar(select(func.count()).select_from(WalletLedger)) or 0) == 2
    assert int(await db.scalar(select(func.count()).select_from(UserEntitlement)) or 0) == 1


async def test_insufficient_coins_does_not_create_financial_records(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
) -> None:
    await enable_flag(db, "coins_enabled")
    episode = await paid_episode(db, price=50)
    response = await client.post(
        f"/api/v1/episodes/{episode.id}/unlock",
        headers={
            "Authorization": f"Bearer {registered['access_token']}",
            "Idempotency-Key": "unlock-insufficient-001",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INSUFFICIENT_COINS"
    assert int(await db.scalar(select(func.count()).select_from(WalletLedger)) or 0) == 0
    assert int(await db.scalar(select(func.count()).select_from(EpisodeUnlock)) or 0) == 0


async def test_packages_checkout_and_idempotent_payment_webhook(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    fake_payment_provider: FakePaymentProvider,
) -> None:
    await enable_flag(db, "coins_enabled")
    package = CoinPackage(
        name="Starter Coins",
        coins=100,
        bonus_coins=20,
        price=Decimal("4.99"),
        currency="USD",
        platform=PaymentPlatform.WEB,
        active=True,
        featured=True,
    )
    db.add(package)
    await db.commit()
    packages = await client.get("/api/v1/coins/packages?platform=web")
    assert packages.status_code == 200
    assert packages.json()["data"][0]["coins"] == 100

    headers = {
        "Authorization": f"Bearer {registered['access_token']}",
        "Idempotency-Key": "coin-checkout-001",
    }
    checkout = await client.post(
        "/api/v1/coins/purchase", headers=headers, json={"product_id": str(package.id)}
    )
    assert checkout.status_code == 201, checkout.text
    payment_id = UUID(checkout.json()["data"]["payment_id"])
    payment = await db.get(Payment, payment_id)
    assert payment is not None
    event = ProviderEvent(
        event_id="evt_coin_paid_001",
        event_type="checkout.session.completed",
        provider_transaction_id=payment.provider_transaction_id,
        payment_id=str(payment.id),
        status="paid",
    )
    first, first_duplicate = await process_payment_webhook(
        db, provider=fake_payment_provider, event=event
    )
    second, second_duplicate = await process_payment_webhook(
        db, provider=fake_payment_provider, event=event
    )
    assert first.status.value == "completed"
    assert first_duplicate is False and second_duplicate is True
    assert first.id == second.id
    wallet = (await client.get("/api/v1/wallet", headers=headers)).json()["data"]
    assert wallet["coin_balance"] == 100
    assert wallet["bonus_coin_balance"] == 20
    assert int(await db.scalar(select(func.count()).select_from(PaymentEvent)) or 0) == 1


async def test_active_subscription_is_returned(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
) -> None:
    await enable_flag(db, "subscriptions_enabled")
    plan = SubscriptionPlan(
        name="Drovixa Annual",
        slug="drovixa-annual",
        interval=SubscriptionInterval.ANNUAL,
        price=Decimal("59.99"),
        currency="USD",
        active=True,
        benefits={"no_ads": True, "full_hd": True, "device_limit": 4},
        store_product_ids={},
    )
    user_id = UUID(str(registered["user"]["id"]))
    now = utcnow()
    subscription = Subscription(
        user_id=user_id,
        plan=plan,
        provider="stripe",
        provider_subscription_id="sub_active_001",
        status=SubscriptionStatus.ACTIVE,
        starts_at=now,
        current_period_start=now,
        current_period_end=now + timedelta(days=365),
        subscription_metadata={},
    )
    db.add_all([plan, subscription])
    await db.commit()
    plans = await client.get("/api/v1/subscriptions/plans")
    assert plans.status_code == 200
    assert plans.json()["data"][0]["benefits"]["no_ads"] is True
    current = await client.get(
        "/api/v1/subscriptions/current",
        headers={"Authorization": f"Bearer {registered['access_token']}"},
    )
    assert current.status_code == 200
    assert current.json()["data"]["plan"]["slug"] == "drovixa-annual"
