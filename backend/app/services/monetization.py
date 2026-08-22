from __future__ import annotations

from calendar import monthrange
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.integrations.payments import (
    CheckoutRequest,
    MobileReceiptVerifier,
    PaymentProvider,
    ProviderEvent,
)
from app.models.base import utcnow
from app.models.content import Episode, Series
from app.models.enums import (
    ContentStatus,
    ContentType,
    EpisodeAccessType,
    LedgerStatus,
    PaymentPlatform,
    PaymentProductType,
    PaymentStatus,
    SubscriptionInterval,
    SubscriptionStatus,
    WalletTransactionType,
)
from app.models.monetization import (
    CoinPackage,
    EpisodeUnlock,
    Payment,
    PaymentEvent,
    Subscription,
    SubscriptionPlan,
    Wallet,
    WalletLedger,
)
from app.models.streaming import UserEntitlement
from app.models.user import User
from app.schemas.monetization import MobilePurchaseVerifyInput


def wallet_data(wallet: Wallet) -> dict[str, Any]:
    return {
        "user_id": wallet.user_id,
        "coin_balance": wallet.coin_balance,
        "bonus_coin_balance": wallet.bonus_coin_balance,
        "total_balance": wallet.coin_balance + wallet.bonus_coin_balance,
        "updated_at": wallet.updated_at,
    }


def ledger_data(row: WalletLedger) -> dict[str, Any]:
    return {
        "id": row.id,
        "type": row.type,
        "amount": row.amount,
        "balance_before": row.balance_before,
        "balance_after": row.balance_after,
        "reference": row.reference,
        "source": row.source,
        "status": row.status,
        "metadata": row.transaction_metadata,
        "created_at": row.created_at,
    }


def package_data(row: CoinPackage) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "coins": row.coins,
        "bonus_coins": row.bonus_coins,
        "price": row.price,
        "currency": row.currency,
        "platform": row.platform,
        "store_product_id": row.store_product_id,
        "country_id": row.country_id,
        "active": row.active,
        "featured": row.featured,
        "sort_order": row.sort_order,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def plan_data(row: SubscriptionPlan) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "slug": row.slug,
        "interval": row.interval,
        "price": row.price,
        "currency": row.currency,
        "active": row.active,
        "featured": row.featured,
        "trial_days": row.trial_days,
        "provider_price_id": row.provider_price_id,
        "store_product_ids": row.store_product_ids,
        "benefits": row.benefits,
        "sort_order": row.sort_order,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def subscription_data(row: Subscription) -> dict[str, Any]:
    return {
        "id": row.id,
        "plan": plan_data(row.plan),
        "provider": row.provider,
        "status": row.status,
        "starts_at": row.starts_at,
        "current_period_start": row.current_period_start,
        "current_period_end": row.current_period_end,
        "cancel_at_period_end": row.cancel_at_period_end,
        "cancelled_at": row.cancelled_at,
        "ended_at": row.ended_at,
    }


async def get_or_create_wallet(db: AsyncSession, *, user_id: UUID, lock: bool = False) -> Wallet:
    statement = select(Wallet).where(Wallet.user_id == user_id)
    if lock:
        statement = statement.with_for_update()
    wallet = await db.scalar(statement)
    if wallet is None:
        wallet = Wallet(user_id=user_id, coin_balance=0, bonus_coin_balance=0)
        db.add(wallet)
        await db.flush()
    return wallet


async def wallet_transactions(
    db: AsyncSession, *, user_id: UUID, page: int, limit: int
) -> tuple[list[dict[str, Any]], int]:
    filters = (WalletLedger.user_id == user_id,)
    total = int(
        await db.scalar(select(func.count()).select_from(WalletLedger).where(*filters)) or 0
    )
    rows = (
        await db.scalars(
            select(WalletLedger)
            .where(*filters)
            .order_by(WalletLedger.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()
    return [ledger_data(row) for row in rows], total


async def active_coin_packages(
    db: AsyncSession, *, platform: PaymentPlatform | None = None
) -> list[CoinPackage]:
    statement = select(CoinPackage).where(
        CoinPackage.active.is_(True), CoinPackage.deleted_at.is_(None)
    )
    if platform:
        statement = statement.where(CoinPackage.platform == platform)
    return list(
        (
            await db.scalars(
                statement.order_by(
                    CoinPackage.featured.desc(), CoinPackage.sort_order, CoinPackage.coins
                )
            )
        ).all()
    )


async def active_subscription_plans(db: AsyncSession) -> list[SubscriptionPlan]:
    return list(
        (
            await db.scalars(
                select(SubscriptionPlan)
                .where(SubscriptionPlan.active.is_(True), SubscriptionPlan.deleted_at.is_(None))
                .order_by(
                    SubscriptionPlan.featured.desc(),
                    SubscriptionPlan.sort_order,
                    SubscriptionPlan.price,
                )
            )
        ).all()
    )


def _apply_wallet_change(
    wallet: Wallet,
    *,
    regular_delta: int,
    bonus_delta: int,
    transaction_type: WalletTransactionType,
    source: str,
    idempotency_key: str,
    reference: str | None,
    metadata: dict[str, Any],
) -> WalletLedger:
    before_regular = wallet.coin_balance
    before_bonus = wallet.bonus_coin_balance
    after_regular = before_regular + regular_delta
    after_bonus = before_bonus + bonus_delta
    if after_regular < 0 or after_bonus < 0:
        raise AppError("INSUFFICIENT_COINS", "You do not have enough coins.", status_code=409)
    wallet.coin_balance = after_regular
    wallet.bonus_coin_balance = after_bonus
    row = WalletLedger(
        user_id=wallet.user_id,
        type=transaction_type,
        amount=regular_delta + bonus_delta,
        balance_before=before_regular + before_bonus,
        balance_after=after_regular + after_bonus,
        coin_balance_before=before_regular,
        coin_balance_after=after_regular,
        bonus_balance_before=before_bonus,
        bonus_balance_after=after_bonus,
        reference=reference,
        source=source,
        status=LedgerStatus.COMPLETED,
        idempotency_key=idempotency_key,
        transaction_metadata=metadata,
    )
    return row


async def adjust_wallet(
    db: AsyncSession,
    *,
    user_id: UUID,
    amount: int,
    bonus_amount: int,
    reason: str,
    admin_id: UUID,
    idempotency_key: str,
) -> tuple[Wallet, WalletLedger]:
    user_exists = await db.scalar(
        select(User.id).where(User.id == user_id, User.deleted_at.is_(None))
    )
    if user_exists is None:
        raise AppError("NOT_FOUND", "User not found.", status_code=404)
    existing = await db.scalar(
        select(WalletLedger).where(
            WalletLedger.user_id == user_id,
            WalletLedger.idempotency_key == idempotency_key,
        )
    )
    wallet = await get_or_create_wallet(db, user_id=user_id, lock=True)
    if existing:
        return wallet, existing
    ledger = _apply_wallet_change(
        wallet,
        regular_delta=amount,
        bonus_delta=bonus_amount,
        transaction_type=WalletTransactionType.ADMIN_ADJUSTMENT,
        source="admin",
        idempotency_key=idempotency_key,
        reference=str(admin_id),
        metadata={"reason": reason, "admin_id": str(admin_id)},
    )
    db.add(ledger)
    await db.flush()
    return wallet, ledger


async def unlock_episode(
    db: AsyncSession, *, user_id: UUID, episode_id: UUID, idempotency_key: str
) -> dict[str, Any]:
    existing_ledger = await db.scalar(
        select(WalletLedger).where(
            WalletLedger.user_id == user_id,
            WalletLedger.idempotency_key == idempotency_key,
        )
    )
    wallet = await get_or_create_wallet(db, user_id=user_id, lock=True)
    if existing_ledger:
        unlock = await db.scalar(
            select(EpisodeUnlock).where(EpisodeUnlock.ledger_transaction_id == existing_ledger.id)
        )
        if unlock is None or unlock.episode_id != episode_id:
            raise AppError(
                "IDEMPOTENCY_KEY_REUSED",
                "This idempotency key belongs to another operation.",
                status_code=409,
            )
        return {
            "episode_id": episode_id,
            "unlocked": True,
            "already_unlocked": False,
            "wallet": wallet_data(wallet),
            "transaction": ledger_data(existing_ledger),
        }
    previous = await db.scalar(
        select(EpisodeUnlock).where(
            EpisodeUnlock.user_id == user_id, EpisodeUnlock.episode_id == episode_id
        )
    )
    if previous:
        return {
            "episode_id": episode_id,
            "unlocked": True,
            "already_unlocked": True,
            "wallet": wallet_data(wallet),
            "transaction": None,
        }
    episode = await db.scalar(
        select(Episode).where(Episode.id == episode_id, Episode.deleted_at.is_(None))
    )
    if episode is None or episode.status != ContentStatus.PUBLISHED:
        raise AppError("NOT_FOUND", "Episode not found.", status_code=404)
    if episode.access_type not in {
        EpisodeAccessType.COIN_UNLOCK,
        EpisodeAccessType.PREMIUM_OR_COIN,
    }:
        raise AppError(
            "EPISODE_NOT_COIN_UNLOCKABLE",
            "This episode cannot be unlocked with coins.",
            status_code=409,
        )
    if episode.coin_price <= 0:
        raise AppError(
            "INVALID_COIN_PRICE", "This episode has no valid coin price.", status_code=409
        )
    price = episode.coin_price
    if wallet.coin_balance + wallet.bonus_coin_balance < price:
        raise AppError("INSUFFICIENT_COINS", "You do not have enough coins.", status_code=409)
    bonus_spend = min(wallet.bonus_coin_balance, price)
    regular_spend = price - bonus_spend
    ledger = _apply_wallet_change(
        wallet,
        regular_delta=-regular_spend,
        bonus_delta=-bonus_spend,
        transaction_type=WalletTransactionType.EPISODE_UNLOCK,
        source="episode_unlock",
        idempotency_key=idempotency_key,
        reference=str(episode_id),
        metadata={"episode_id": str(episode_id), "coin_price": price},
    )
    db.add(ledger)
    await db.flush()
    series_id = await db.scalar(select(Series.id).where(Series.id == episode.series_id))
    if series_id is None:
        raise AppError("CONTENT_NOT_AVAILABLE", "Series not found.", status_code=409)
    db.add(
        EpisodeUnlock(
            user_id=user_id,
            episode_id=episode_id,
            ledger_transaction_id=ledger.id,
            coin_price=price,
        )
    )
    db.add(
        UserEntitlement(
            user_id=user_id,
            content_type=ContentType.SERIES,
            content_id=episode.series_id,
            episode_id=episode_id,
            source="coin_unlock",
            transaction_id=ledger.id,
            starts_at=utcnow(),
            expires_at=None,
            is_permanent=True,
        )
    )
    await db.commit()
    return {
        "episode_id": episode_id,
        "unlocked": True,
        "already_unlocked": False,
        "wallet": wallet_data(wallet),
        "transaction": ledger_data(ledger),
    }


async def create_checkout(
    db: AsyncSession,
    *,
    provider: PaymentProvider,
    user: User,
    product_type: PaymentProductType,
    product_id: UUID,
    idempotency_key: str,
    success_url: str | None,
    cancel_url: str | None,
    country: str | None,
) -> dict[str, Any]:
    existing = await db.scalar(
        select(Payment).where(
            Payment.user_id == user.id, Payment.idempotency_key == idempotency_key
        )
    )
    if existing:
        if existing.product_id != product_id or existing.product_type != product_type:
            raise AppError(
                "IDEMPOTENCY_KEY_REUSED",
                "This idempotency key belongs to another payment.",
                status_code=409,
            )
        checkout_url = existing.payment_metadata.get("checkout_url")
        return {
            "payment_id": existing.id,
            "status": existing.status,
            "checkout_url": checkout_url,
            "provider": existing.provider,
        }
    product_name: str
    provider_price_id: str | None = None
    subscription = product_type == PaymentProductType.SUBSCRIPTION
    interval: str | None = None
    if product_type == PaymentProductType.COINS:
        package = await db.scalar(
            select(CoinPackage).where(
                CoinPackage.id == product_id,
                CoinPackage.active.is_(True),
                CoinPackage.deleted_at.is_(None),
                CoinPackage.platform == PaymentPlatform.WEB,
            )
        )
        if package is None:
            raise AppError("NOT_FOUND", "Coin package not found.", status_code=404)
        product_name, amount, currency = package.name, package.price, package.currency
    else:
        plan = await db.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.id == product_id,
                SubscriptionPlan.active.is_(True),
                SubscriptionPlan.deleted_at.is_(None),
            )
        )
        if plan is None:
            raise AppError("NOT_FOUND", "Subscription plan not found.", status_code=404)
        product_name, amount, currency = plan.name, plan.price, plan.currency
        provider_price_id, interval = plan.provider_price_id, plan.interval.value
    payment = Payment(
        user_id=user.id,
        provider=provider.name,
        product_type=product_type,
        product_id=product_id,
        currency=currency,
        amount=amount,
        status=PaymentStatus.PENDING,
        platform=PaymentPlatform.WEB,
        country=country,
        idempotency_key=idempotency_key,
        payment_metadata={},
    )
    db.add(payment)
    await db.flush()
    await db.commit()
    settings = get_settings()
    try:
        checkout = await provider.create_checkout(
            CheckoutRequest(
                payment_id=str(payment.id),
                idempotency_key=idempotency_key,
                product_name=product_name,
                product_type=product_type.value,
                currency=currency,
                amount=amount,
                quantity=1,
                customer_email=user.email,
                success_url=success_url or settings.PAYMENT_SUCCESS_URL,
                cancel_url=cancel_url or settings.PAYMENT_CANCEL_URL,
                provider_price_id=provider_price_id,
                subscription=subscription,
                metadata={"user_id": str(user.id), "interval": interval or ""},
            )
        )
    except AppError:
        payment.status = PaymentStatus.FAILED
        await db.commit()
        raise
    payment.provider_transaction_id = checkout.provider_transaction_id
    payment.status = PaymentStatus.PROCESSING
    payment.payment_metadata = {
        "checkout_url": checkout.checkout_url,
        "provider_status": checkout.status,
    }
    await db.commit()
    return {
        "payment_id": payment.id,
        "status": payment.status,
        "checkout_url": checkout.checkout_url,
        "provider": payment.provider,
    }


def _period_end(plan: SubscriptionPlan, start: datetime) -> datetime:
    months = {
        SubscriptionInterval.MONTHLY: 1,
        SubscriptionInterval.QUARTERLY: 3,
        SubscriptionInterval.ANNUAL: 12,
    }[plan.interval]
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return start.replace(year=year, month=month, day=day)


async def _grant_paid_payment(db: AsyncSession, *, payment: Payment, event: ProviderEvent) -> None:
    if payment.status == PaymentStatus.PAID:
        return
    payment.status = PaymentStatus.PAID
    payment.payment_metadata = {
        **payment.payment_metadata,
        "provider_event_id": event.event_id,
    }
    if payment.product_type == PaymentProductType.COINS:
        package = await db.scalar(select(CoinPackage).where(CoinPackage.id == payment.product_id))
        if package is None:
            raise AppError("PAYMENT_PRODUCT_MISSING", "Payment product not found.", status_code=409)
        wallet = await get_or_create_wallet(db, user_id=payment.user_id, lock=True)
        ledger_key = f"payment:{payment.id}"
        existing = await db.scalar(
            select(WalletLedger.id).where(
                WalletLedger.user_id == payment.user_id,
                WalletLedger.idempotency_key == ledger_key,
            )
        )
        if existing is None:
            ledger = _apply_wallet_change(
                wallet,
                regular_delta=package.coins,
                bonus_delta=package.bonus_coins,
                transaction_type=WalletTransactionType.PURCHASE,
                source=payment.provider,
                idempotency_key=ledger_key,
                reference=str(payment.id),
                metadata={"payment_id": str(payment.id), "package_id": str(package.id)},
            )
            db.add(ledger)
    else:
        plan = await db.scalar(
            select(SubscriptionPlan).where(SubscriptionPlan.id == payment.product_id)
        )
        if plan is None:
            raise AppError("PAYMENT_PRODUCT_MISSING", "Payment product not found.", status_code=409)
        now = utcnow()
        provider_subscription_id = event.subscription_id or event.provider_transaction_id
        subscription = await db.scalar(
            select(Subscription).where(
                Subscription.provider == payment.provider,
                Subscription.provider_subscription_id == provider_subscription_id,
            )
        )
        end = (
            datetime.fromtimestamp(event.period_end, tz=UTC)
            if event.period_end
            else _period_end(plan, now)
        )
        if subscription is None:
            subscription = Subscription(
                user_id=payment.user_id,
                plan_id=plan.id,
                provider=payment.provider,
                provider_subscription_id=provider_subscription_id,
                status=SubscriptionStatus.ACTIVE,
                starts_at=now,
                current_period_start=now,
                current_period_end=end,
                cancel_at_period_end=False,
                subscription_metadata={"payment_id": str(payment.id)},
            )
            db.add(subscription)
        else:
            subscription.status = SubscriptionStatus.ACTIVE
            subscription.current_period_end = end
            subscription.ended_at = None


async def process_payment_webhook(
    db: AsyncSession, *, provider: PaymentProvider, event: ProviderEvent
) -> tuple[PaymentEvent, bool]:
    existing = await db.scalar(
        select(PaymentEvent).where(PaymentEvent.provider_event_id == event.event_id)
    )
    if existing and existing.status != LedgerStatus.FAILED:
        return existing, True
    payment: Payment | None = None
    if event.payment_id:
        try:
            payment_uuid = UUID(event.payment_id)
        except ValueError:
            payment_uuid = None
        if payment_uuid:
            payment = await db.scalar(
                select(Payment).where(Payment.id == payment_uuid).with_for_update()
            )
    if payment is None and event.provider_transaction_id:
        payment = await db.scalar(
            select(Payment)
            .where(
                Payment.provider == provider.name,
                Payment.provider_transaction_id == event.provider_transaction_id,
            )
            .with_for_update()
        )
    row = existing or PaymentEvent(
        provider=provider.name,
        provider_event_id=event.event_id,
        event_type=event.event_type,
        status=LedgerStatus.PENDING,
        payload=event.raw,
        raw_reference={},
    )
    row.payment_id = payment.id if payment else None
    row.status = LedgerStatus.PENDING
    row.payload = event.raw
    row.raw_reference = {
        "provider_transaction_id": event.provider_transaction_id,
        "payment_id": event.payment_id,
        "subscription_id": event.subscription_id,
    }
    row.error_message = None
    if existing is None:
        db.add(row)
    await db.flush()
    try:
        paid_event = event.event_type in {
            "checkout.session.completed",
            "checkout.session.async_payment_succeeded",
            "invoice.paid",
        }
        if paid_event and payment:
            await _grant_paid_payment(db, payment=payment, event=event)
            row.status = LedgerStatus.COMPLETED
        elif paid_event and event.subscription_id:
            subscription = await db.scalar(
                select(Subscription)
                .where(
                    Subscription.provider == provider.name,
                    Subscription.provider_subscription_id == event.subscription_id,
                )
                .with_for_update()
            )
            if subscription and event.period_end:
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.current_period_start = utcnow()
                subscription.current_period_end = datetime.fromtimestamp(event.period_end, tz=UTC)
                subscription.ended_at = None
            row.status = LedgerStatus.COMPLETED
        elif (
            event.event_type
            in {
                "checkout.session.async_payment_failed",
                "payment_intent.payment_failed",
            }
            and payment
        ):
            payment.status = PaymentStatus.FAILED
            row.status = LedgerStatus.COMPLETED
        elif event.event_type.startswith("customer.subscription.") and event.subscription_id:
            subscription = await db.scalar(
                select(Subscription)
                .where(
                    Subscription.provider == provider.name,
                    Subscription.provider_subscription_id == event.subscription_id,
                )
                .with_for_update()
            )
            if subscription:
                provider_status = (event.status or "").lower()
                normalized_status = {
                    "trialing": SubscriptionStatus.TRIALING,
                    "active": SubscriptionStatus.ACTIVE,
                    "past_due": SubscriptionStatus.PAST_DUE,
                    "canceled": SubscriptionStatus.CANCELLED,
                    "cancelled": SubscriptionStatus.CANCELLED,
                    "unpaid": SubscriptionStatus.EXPIRED,
                }.get(provider_status)
                if normalized_status:
                    subscription.status = normalized_status
                if event.period_end:
                    subscription.current_period_end = datetime.fromtimestamp(
                        event.period_end, tz=UTC
                    )
                if event.event_type == "customer.subscription.deleted":
                    subscription.status = SubscriptionStatus.CANCELLED
                    subscription.ended_at = utcnow()
            row.status = LedgerStatus.COMPLETED
        else:
            row.status = LedgerStatus.COMPLETED
        row.processed_at = utcnow()
        await db.commit()
    except Exception as exc:
        await db.rollback()
        failed = await db.scalar(
            select(PaymentEvent).where(PaymentEvent.provider_event_id == event.event_id)
        )
        if failed is None:
            failed = PaymentEvent(
                provider=provider.name,
                provider_event_id=event.event_id,
                event_type=event.event_type,
                payment_id=payment.id if payment else None,
                payload=event.raw,
                raw_reference={
                    "provider_transaction_id": event.provider_transaction_id,
                    "payment_id": event.payment_id,
                    "subscription_id": event.subscription_id,
                },
            )
            db.add(failed)
        failed.status = LedgerStatus.FAILED
        failed.error_message = str(exc)[:1000]
        await db.commit()
        raise
    return row, False


async def current_subscription(db: AsyncSession, *, user_id: UUID) -> Subscription | None:
    now = utcnow()
    return cast(
        Subscription | None,
        await db.scalar(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_([SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE]),
                Subscription.current_period_end > now,
            )
            .order_by(Subscription.current_period_end.desc())
        ),
    )


async def has_active_subscription(db: AsyncSession, *, user_id: UUID) -> bool:
    return await current_subscription(db, user_id=user_id) is not None


async def cancel_current_subscription(
    db: AsyncSession, *, provider: PaymentProvider, user_id: UUID, reason: str | None
) -> Subscription:
    subscription = await current_subscription(db, user_id=user_id)
    if subscription is None:
        raise AppError("NOT_FOUND", "No active subscription was found.", status_code=404)
    if subscription.provider in {"apple_iap", "google_play"}:
        raise AppError(
            "MANAGE_SUBSCRIPTION_IN_STORE",
            "Manage this subscription in your device store.",
            status_code=409,
            details={"provider": subscription.provider},
        )
    if subscription.provider != provider.name:
        raise AppError(
            "PAYMENT_PROVIDER_UNAVAILABLE",
            "The subscription payment provider is not available.",
            status_code=503,
        )
    if subscription.provider_subscription_id:
        await provider.cancel_subscription(subscription.provider_subscription_id)
    subscription.cancel_at_period_end = True
    subscription.cancelled_at = utcnow()
    subscription.subscription_metadata = {
        **subscription.subscription_metadata,
        "cancellation_reason": reason,
    }
    await db.commit()
    return subscription


async def verify_mobile_purchase(
    db: AsyncSession,
    *,
    verifier: MobileReceiptVerifier,
    user_id: UUID,
    payload: MobilePurchaseVerifyInput,
    idempotency_key: str,
) -> dict[str, Any]:
    existing = await db.scalar(
        select(Payment).where(
            Payment.user_id == user_id, Payment.idempotency_key == idempotency_key
        )
    )
    if existing:
        return {"payment_id": existing.id, "status": existing.status, "verified": True}
    verified = await verifier.verify(
        platform=payload.platform.value,
        product_id=payload.store_product_id,
        transaction_id=payload.transaction_id,
        receipt=payload.receipt,
    )
    if not verified.active or verified.product_id != payload.store_product_id:
        raise AppError("IAP_VERIFICATION_FAILED", "The store receipt is invalid.", status_code=409)
    product_type = PaymentProductType(payload.product_type)
    if product_type == PaymentProductType.COINS:
        product = await db.scalar(
            select(CoinPackage).where(
                CoinPackage.id == payload.product_id,
                CoinPackage.platform == payload.platform,
                CoinPackage.store_product_id == payload.store_product_id,
                CoinPackage.active.is_(True),
            )
        )
    else:
        product = await db.scalar(
            select(SubscriptionPlan).where(
                SubscriptionPlan.id == payload.product_id,
                SubscriptionPlan.active.is_(True),
            )
        )
        if (
            product
            and product.store_product_ids.get(payload.platform.value) != payload.store_product_id
        ):
            product = None
    if product is None:
        raise AppError("NOT_FOUND", "Store product not found.", status_code=404)
    payment = Payment(
        user_id=user_id,
        provider="apple_iap" if payload.platform == PaymentPlatform.IOS else "google_play",
        provider_transaction_id=verified.transaction_id,
        product_type=product_type,
        product_id=payload.product_id,
        currency=product.currency,
        amount=product.price,
        status=PaymentStatus.PROCESSING,
        platform=payload.platform,
        country=None,
        idempotency_key=idempotency_key,
        payment_metadata={"store_product_id": verified.product_id},
    )
    db.add(payment)
    await db.flush()
    event = ProviderEvent(
        event_id=f"iap:{payment.provider}:{verified.transaction_id}",
        event_type="iap.verified",
        provider_transaction_id=verified.transaction_id,
        payment_id=str(payment.id),
        status="paid",
        subscription_id=verified.transaction_id
        if product_type == PaymentProductType.SUBSCRIPTION
        else None,
        raw=verified.raw_reference,
    )
    await _grant_paid_payment(db, payment=payment, event=event)
    await db.commit()
    return {"payment_id": payment.id, "status": payment.status, "verified": True}
