from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status

from app.api.deps import CurrentContext, DbSession, require_feature_enabled
from app.core.rate_limit import rate_limit
from app.integrations.payments import (
    MobileReceiptVerifier,
    PaymentProvider,
    get_mobile_receipt_verifier,
    get_payment_provider,
)
from app.models.enums import PaymentPlatform, PaymentProductType
from app.schemas.common import success
from app.schemas.monetization import (
    CheckoutInput,
    MobilePurchaseVerifyInput,
    SubscriptionCancelInput,
)
from app.services.monetization import (
    active_coin_packages,
    active_subscription_plans,
    cancel_current_subscription,
    create_checkout,
    current_subscription,
    get_or_create_wallet,
    package_data,
    plan_data,
    subscription_data,
    unlock_episode,
    verify_mobile_purchase,
    wallet_data,
    wallet_transactions,
)

router = APIRouter(tags=["Monetization"])
Provider = Annotated[PaymentProvider, Depends(get_payment_provider)]
ReceiptVerifier = Annotated[MobileReceiptVerifier, Depends(get_mobile_receipt_verifier)]
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]


def _meta(page: int, limit: int, total: int) -> dict[str, int]:
    return {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit}


@router.get("/wallet")
async def get_wallet(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    wallet = await get_or_create_wallet(db, user_id=context.user.id)
    await db.commit()
    return success(wallet_data(wallet))


@router.get("/wallet/transactions")
async def get_wallet_transactions(
    context: CurrentContext, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    rows, total = await wallet_transactions(db, user_id=context.user.id, page=page, limit=limit)
    return success(rows, meta=_meta(page, limit, total))


@router.get(
    "/coins/packages",
    dependencies=[require_feature_enabled("coins_enabled", error_code="COINS_DISABLED")],
)
async def get_coin_packages(
    db: DbSession, platform: PaymentPlatform | None = None
) -> dict[str, Any]:
    rows = await active_coin_packages(db, platform=platform)
    return success([package_data(row) for row in rows])


@router.post(
    "/coins/purchase",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        require_feature_enabled("coins_enabled", error_code="COINS_DISABLED"),
        Depends(rate_limit("coin_purchase", requests=10, window_seconds=60)),
    ],
)
async def purchase_coins(
    payload: CheckoutInput,
    idempotency_key: IdempotencyKey,
    context: CurrentContext,
    db: DbSession,
    provider: Provider,
) -> dict[str, Any]:
    return success(
        await create_checkout(
            db,
            provider=provider,
            user=context.user,
            product_type=PaymentProductType.COINS,
            product_id=payload.product_id,
            idempotency_key=idempotency_key,
            success_url=str(payload.success_url) if payload.success_url else None,
            cancel_url=str(payload.cancel_url) if payload.cancel_url else None,
            country=payload.country,
        )
    )


@router.post(
    "/episodes/{episode_id}/unlock",
    dependencies=[
        require_feature_enabled("coins_enabled", error_code="COINS_DISABLED"),
        Depends(rate_limit("episode_unlock", requests=20, window_seconds=60)),
    ],
)
async def unlock_paid_episode(
    episode_id: UUID,
    idempotency_key: IdempotencyKey,
    context: CurrentContext,
    db: DbSession,
) -> dict[str, Any]:
    return success(
        await unlock_episode(
            db,
            user_id=context.user.id,
            episode_id=episode_id,
            idempotency_key=idempotency_key,
        )
    )


@router.get(
    "/subscriptions/plans",
    dependencies=[
        require_feature_enabled("subscriptions_enabled", error_code="SUBSCRIPTIONS_DISABLED")
    ],
)
async def get_subscription_plans(db: DbSession) -> dict[str, Any]:
    rows = await active_subscription_plans(db)
    return success([plan_data(row) for row in rows])


@router.post(
    "/subscriptions/checkout",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        require_feature_enabled("subscriptions_enabled", error_code="SUBSCRIPTIONS_DISABLED"),
        Depends(rate_limit("subscription_checkout", requests=10, window_seconds=60)),
    ],
)
async def subscription_checkout(
    payload: CheckoutInput,
    idempotency_key: IdempotencyKey,
    context: CurrentContext,
    db: DbSession,
    provider: Provider,
) -> dict[str, Any]:
    return success(
        await create_checkout(
            db,
            provider=provider,
            user=context.user,
            product_type=PaymentProductType.SUBSCRIPTION,
            product_id=payload.product_id,
            idempotency_key=idempotency_key,
            success_url=str(payload.success_url) if payload.success_url else None,
            cancel_url=str(payload.cancel_url) if payload.cancel_url else None,
            country=payload.country,
        )
    )


@router.get("/subscriptions/current")
async def get_current_subscription(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    row = await current_subscription(db, user_id=context.user.id)
    return success(subscription_data(row) if row else None)


@router.post("/subscriptions/cancel")
async def cancel_subscription(
    payload: SubscriptionCancelInput,
    context: CurrentContext,
    db: DbSession,
    provider: Provider,
) -> dict[str, Any]:
    row = await cancel_current_subscription(
        db,
        provider=provider,
        user_id=context.user.id,
        reason=payload.reason,
    )
    return success(subscription_data(row))


@router.post("/subscriptions/restore")
async def restore_subscription() -> dict[str, Any]:
    # Native restore operations submit the resulting store receipt to /iap/verify.
    return success({"verification_endpoint": "/api/v1/iap/verify", "restored": False})


@router.post(
    "/iap/verify",
    dependencies=[Depends(rate_limit("iap_verify", requests=10, window_seconds=60))],
)
async def verify_iap(
    payload: MobilePurchaseVerifyInput,
    idempotency_key: IdempotencyKey,
    context: CurrentContext,
    db: DbSession,
    verifier: ReceiptVerifier,
) -> dict[str, Any]:
    return success(
        await verify_mobile_purchase(
            db,
            verifier=verifier,
            user_id=context.user.id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    )
