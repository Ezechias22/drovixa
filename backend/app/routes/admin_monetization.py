from __future__ import annotations

from datetime import UTC, timedelta
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select

from app.api.deps import DbSession, require_permission
from app.core.exceptions import AppError
from app.models.base import utcnow
from app.models.enums import SubscriptionInterval, SubscriptionStatus
from app.models.monetization import CoinPackage, Payment, Subscription, SubscriptionPlan, Wallet
from app.models.user import User
from app.schemas.common import success
from app.schemas.monetization import (
    AdminSubscriptionGrantInput,
    AdminSubscriptionRevokeInput,
    CoinPackageCreate,
    CoinPackageUpdate,
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    WalletAdjustmentInput,
)
from app.services.audit import add_audit_log
from app.services.monetization import (
    adjust_wallet,
    current_subscription,
    ledger_data,
    package_data,
    plan_data,
    subscription_data,
    wallet_data,
)

router = APIRouter(prefix="/admin", tags=["Admin monetization"])
WalletViewer = Annotated[User, require_permission("wallet.view")]
WalletManager = Annotated[User, require_permission("wallet.adjust")]
PaymentsViewer = Annotated[User, require_permission("payments.view")]
SubscriptionManager = Annotated[User, require_permission("subscriptions.manage")]
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]
ADMIN_PREMIUM_PLAN_SLUG = "drovixa-internal-admin-premium"
IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]


def _meta(page: int, limit: int, total: int) -> dict[str, int]:
    return {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit}


async def _coin_package(db: DbSession, package_id: UUID) -> CoinPackage:
    row = await db.scalar(
        select(CoinPackage).where(CoinPackage.id == package_id, CoinPackage.deleted_at.is_(None))
    )
    if row is None:
        raise AppError("NOT_FOUND", "Coin package not found.", status_code=404)
    return row


async def _subscription_plan(db: DbSession, plan_id: UUID) -> SubscriptionPlan:
    row = await db.scalar(
        select(SubscriptionPlan).where(
            SubscriptionPlan.id == plan_id, SubscriptionPlan.deleted_at.is_(None)
        )
    )
    if row is None:
        raise AppError("NOT_FOUND", "Subscription plan not found.", status_code=404)
    return row


async def _admin_premium_plan(db: DbSession) -> SubscriptionPlan:
    row = await db.scalar(
        select(SubscriptionPlan).where(SubscriptionPlan.slug == ADMIN_PREMIUM_PLAN_SLUG)
    )
    if row is None:
        row = SubscriptionPlan(
            name="Admin Premium",
            slug=ADMIN_PREMIUM_PLAN_SLUG,
            interval=SubscriptionInterval.MONTHLY,
            price=Decimal("0.01"),
            currency="USD",
            active=False,
            featured=False,
            trial_days=0,
            benefits={"internal_admin_grant": True},
            sort_order=9999,
        )
        db.add(row)
        await db.flush()
    return row


@router.get("/coin-packages")
async def admin_coin_packages(
    _: WalletViewer, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    filters = (CoinPackage.deleted_at.is_(None),)
    total = int(await db.scalar(select(func.count()).select_from(CoinPackage).where(*filters)) or 0)
    rows = (
        await db.scalars(
            select(CoinPackage)
            .where(*filters)
            .order_by(CoinPackage.sort_order, CoinPackage.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()
    return success([package_data(row) for row in rows], meta=_meta(page, limit, total))


@router.post("/coin-packages", status_code=status.HTTP_201_CREATED)
async def create_coin_package(
    payload: CoinPackageCreate,
    request: Request,
    admin: WalletManager,
    db: DbSession,
) -> dict[str, Any]:
    row = CoinPackage(**payload.model_dump())
    db.add(row)
    await db.flush()
    snapshot = package_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="coin_package.create",
        entity_type="coin_package",
        entity_id=str(row.id),
        old_value=None,
        new_value=jsonable_encoder(snapshot),
    )
    await db.commit()
    return success(snapshot)


@router.patch("/coin-packages/{package_id}")
async def update_coin_package(
    package_id: UUID,
    payload: CoinPackageUpdate,
    request: Request,
    admin: WalletManager,
    db: DbSession,
) -> dict[str, Any]:
    row = await _coin_package(db, package_id)
    old = package_data(row)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await db.flush()
    new = package_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="coin_package.update",
        entity_type="coin_package",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(new),
    )
    await db.commit()
    return success(new)


@router.delete("/coin-packages/{package_id}")
async def archive_coin_package(
    package_id: UUID, request: Request, admin: WalletManager, db: DbSession
) -> dict[str, Any]:
    row = await _coin_package(db, package_id)
    old = package_data(row)
    row.active = False
    row.deleted_at = utcnow()
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="coin_package.archive",
        entity_type="coin_package",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder({"active": False, "deleted_at": row.deleted_at}),
    )
    await db.commit()
    return success({"id": row.id, "archived": True})


@router.get("/subscription-plans")
async def admin_subscription_plans(
    _: SubscriptionManager, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    filters = (SubscriptionPlan.deleted_at.is_(None),)
    total = int(
        await db.scalar(select(func.count()).select_from(SubscriptionPlan).where(*filters)) or 0
    )
    rows = (
        await db.scalars(
            select(SubscriptionPlan)
            .where(*filters)
            .order_by(SubscriptionPlan.sort_order, SubscriptionPlan.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()
    return success([plan_data(row) for row in rows], meta=_meta(page, limit, total))


@router.post("/subscription-plans", status_code=status.HTTP_201_CREATED)
async def create_subscription_plan(
    payload: SubscriptionPlanCreate,
    request: Request,
    admin: SubscriptionManager,
    db: DbSession,
) -> dict[str, Any]:
    if await db.scalar(select(SubscriptionPlan.id).where(SubscriptionPlan.slug == payload.slug)):
        raise AppError("CONFLICT", "This subscription plan slug already exists.", status_code=409)
    row = SubscriptionPlan(**payload.model_dump())
    db.add(row)
    await db.flush()
    snapshot = plan_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="subscription_plan.create",
        entity_type="subscription_plan",
        entity_id=str(row.id),
        old_value=None,
        new_value=jsonable_encoder(snapshot),
    )
    await db.commit()
    return success(snapshot)


@router.patch("/subscription-plans/{plan_id}")
async def update_subscription_plan(
    plan_id: UUID,
    payload: SubscriptionPlanUpdate,
    request: Request,
    admin: SubscriptionManager,
    db: DbSession,
) -> dict[str, Any]:
    row = await _subscription_plan(db, plan_id)
    old = plan_data(row)
    changes = payload.model_dump(exclude_unset=True)
    if "slug" in changes and await db.scalar(
        select(SubscriptionPlan.id).where(
            SubscriptionPlan.slug == changes["slug"], SubscriptionPlan.id != row.id
        )
    ):
        raise AppError("CONFLICT", "This subscription plan slug already exists.", status_code=409)
    for key, value in changes.items():
        setattr(row, key, value)
    await db.flush()
    new = plan_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="subscription_plan.update",
        entity_type="subscription_plan",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(new),
    )
    await db.commit()
    return success(new)


@router.delete("/subscription-plans/{plan_id}")
async def archive_subscription_plan(
    plan_id: UUID, request: Request, admin: SubscriptionManager, db: DbSession
) -> dict[str, Any]:
    row = await _subscription_plan(db, plan_id)
    old = plan_data(row)
    row.active = False
    row.deleted_at = utcnow()
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="subscription_plan.archive",
        entity_type="subscription_plan",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder({"active": False, "deleted_at": row.deleted_at}),
    )
    await db.commit()
    return success({"id": row.id, "archived": True})


@router.post("/wallets/{user_id}/adjust")
async def admin_adjust_wallet(
    user_id: UUID,
    payload: WalletAdjustmentInput,
    idempotency_key: IdempotencyKey,
    request: Request,
    admin: WalletManager,
    db: DbSession,
) -> dict[str, Any]:
    wallet, ledger = await adjust_wallet(
        db,
        user_id=user_id,
        amount=payload.amount,
        bonus_amount=payload.bonus_amount,
        reason=payload.reason,
        admin_id=admin.id,
        idempotency_key=idempotency_key,
    )
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="wallet.adjust",
        entity_type="wallet",
        entity_id=str(user_id),
        old_value={"balance": ledger.balance_before},
        new_value={
            "balance": ledger.balance_after,
            "transaction_id": str(ledger.id),
            "reason": payload.reason,
        },
    )
    await db.commit()
    return success({"wallet": wallet_data(wallet), "transaction": ledger_data(ledger)})


@router.get("/users/{user_id}/monetization")
async def admin_user_monetization(
    user_id: UUID,
    _: WalletViewer,
    __: SubscriptionManager,
    db: DbSession,
) -> dict[str, Any]:
    user_exists = await db.scalar(
        select(User.id).where(User.id == user_id, User.deleted_at.is_(None))
    )
    if user_exists is None:
        raise AppError("NOT_FOUND", "User not found.", status_code=404)
    wallet = await db.scalar(select(Wallet).where(Wallet.user_id == user_id))
    subscription = await current_subscription(db, user_id=user_id)
    wallet_snapshot = wallet_data(wallet) if wallet else {
        "user_id": user_id,
        "coin_balance": 0,
        "bonus_coin_balance": 0,
        "total_balance": 0,
        "updated_at": None,
    }
    return success({
        "wallet": wallet_snapshot,
        "subscription": subscription_data(subscription) if subscription else None,
    })


@router.post("/users/{user_id}/premium")
async def admin_grant_premium(
    user_id: UUID,
    payload: AdminSubscriptionGrantInput,
    request: Request,
    admin: SubscriptionManager,
    db: DbSession,
) -> dict[str, Any]:
    user_exists = await db.scalar(
        select(User.id).where(User.id == user_id, User.deleted_at.is_(None))
    )
    if user_exists is None:
        raise AppError("NOT_FOUND", "User not found.", status_code=404)
    plan = (
        await _subscription_plan(db, payload.plan_id)
        if payload.plan_id is not None
        else await _admin_premium_plan(db)
    )
    if payload.plan_id is not None and not plan.active:
        raise AppError("PLAN_INACTIVE", "Activate this plan before assigning it.", status_code=409)
    now = utcnow()
    row = await db.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.provider == "admin_grant",
            Subscription.status.in_([SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE]),
            Subscription.current_period_end > now,
        )
        .order_by(Subscription.current_period_end.desc())
    )
    old = subscription_data(row) if row else None
    if row is None:
        row = Subscription(
            user_id=user_id,
            plan_id=plan.id,
            plan=plan,
            provider="admin_grant",
            provider_subscription_id=f"admin:{user_id}:{uuid4()}",
            status=SubscriptionStatus.ACTIVE,
            starts_at=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=payload.days),
            cancel_at_period_end=False,
            subscription_metadata={},
        )
        db.add(row)
    else:
        row.plan_id = plan.id
        row.plan = plan
        row.status = SubscriptionStatus.ACTIVE
        row.current_period_start = now
        current_end = row.current_period_end
        if current_end.tzinfo is None:
            current_end = current_end.replace(tzinfo=UTC)
        row.current_period_end = max(current_end, now) + timedelta(days=payload.days)
        row.cancel_at_period_end = False
        row.cancelled_at = None
        row.ended_at = None
    row.subscription_metadata = {
        **(row.subscription_metadata or {}),
        "reason": payload.reason,
        "granted_by": str(admin.id),
        "days": payload.days,
    }
    await db.flush()
    snapshot = subscription_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="subscription.admin_grant",
        entity_type="subscription",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(snapshot),
    )
    await db.commit()
    return success(snapshot)


@router.post("/users/{user_id}/premium/revoke")
async def admin_revoke_premium(
    user_id: UUID,
    payload: AdminSubscriptionRevokeInput,
    request: Request,
    admin: SubscriptionManager,
    db: DbSession,
) -> dict[str, Any]:
    now = utcnow()
    row = await db.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.provider == "admin_grant",
            Subscription.status.in_([SubscriptionStatus.TRIALING, SubscriptionStatus.ACTIVE]),
            Subscription.current_period_end > now,
        )
        .order_by(Subscription.current_period_end.desc())
    )
    if row is None:
        raise AppError(
            "NO_ADMIN_PREMIUM",
            (
                "No active admin-assigned Premium access was found. "
                "Paid subscriptions must be managed by their payment provider."
            ),
            status_code=409,
        )
    old = subscription_data(row)
    row.status = SubscriptionStatus.CANCELLED
    row.cancel_at_period_end = False
    row.current_period_end = now
    row.cancelled_at = now
    row.ended_at = now
    row.subscription_metadata = {
        **(row.subscription_metadata or {}),
        "revoke_reason": payload.reason,
        "revoked_by": str(admin.id),
    }
    await db.flush()
    snapshot = subscription_data(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="subscription.admin_revoke",
        entity_type="subscription",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(snapshot),
    )
    await db.commit()
    return success(snapshot)


@router.get("/payments")
async def admin_payments(
    _: PaymentsViewer, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    total = int(await db.scalar(select(func.count()).select_from(Payment)) or 0)
    rows = (
        await db.scalars(
            select(Payment)
            .order_by(Payment.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()
    data = [
        {
            "id": row.id,
            "user_id": row.user_id,
            "provider": row.provider,
            "provider_transaction_id": row.provider_transaction_id,
            "product_type": row.product_type,
            "product_id": row.product_id,
            "currency": row.currency,
            "amount": row.amount,
            "status": row.status,
            "platform": row.platform,
            "country": row.country,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        for row in rows
    ]
    return success(data, meta=_meta(page, limit, total))


@router.get("/subscriptions")
async def admin_subscriptions(
    _: SubscriptionManager, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    total = int(await db.scalar(select(func.count()).select_from(Subscription)) or 0)
    rows = (
        await db.scalars(
            select(Subscription)
            .order_by(Subscription.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()
    return success(
        [{"user_id": row.user_id, **subscription_data(row)} for row in rows],
        meta=_meta(page, limit, total),
    )
