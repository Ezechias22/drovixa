from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select

from app.api.deps import DbSession, require_permission
from app.core.exceptions import AppError
from app.models.base import utcnow
from app.models.monetization import CoinPackage, Payment, Subscription, SubscriptionPlan
from app.models.user import User
from app.schemas.common import success
from app.schemas.monetization import (
    CoinPackageCreate,
    CoinPackageUpdate,
    SubscriptionPlanCreate,
    SubscriptionPlanUpdate,
    WalletAdjustmentInput,
)
from app.services.audit import add_audit_log
from app.services.monetization import (
    adjust_wallet,
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
