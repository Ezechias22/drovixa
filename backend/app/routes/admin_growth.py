from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select

from app.api.deps import DbSession, require_permission
from app.core.exceptions import AppError
from app.models.growth import (
    AdEvent,
    AdPlacement,
    DailyRewardClaim,
    GrowthAutomation,
    GrowthEvent,
    Referral,
    WatchParty,
)
from app.models.user import User
from app.schemas.common import success
from app.schemas.growth import AdPlacementInput, GrowthAutomationUpdate
from app.services.audit import add_audit_log

router = APIRouter(prefix="/admin/growth", tags=["Admin growth"])
GrowthViewer = Annotated[User, require_permission("analytics.view")]
GrowthManager = Annotated[User, require_permission("settings.manage")]


def ad_data(row: AdPlacement) -> dict[str, Any]:
    return {
        "id": row.id,
        "key": row.key,
        "name": row.name,
        "placement": row.placement,
        "format": row.format,
        "headline": row.headline,
        "body": row.body,
        "media_url": row.media_url,
        "click_url": row.click_url,
        "sponsor": row.sponsor,
        "reward_coins": row.reward_coins,
        "daily_cap": row.daily_cap,
        "priority": row.priority,
        "active": row.active,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def automation_data(row: GrowthAutomation) -> dict[str, Any]:
    return {
        "id": row.id,
        "key": row.key,
        "name": row.name,
        "trigger_event": row.trigger_event,
        "action_type": row.action_type,
        "action_config": row.action_config,
        "cooldown_hours": row.cooldown_hours,
        "active": row.active,
        "last_triggered_at": row.last_triggered_at,
        "updated_at": row.updated_at,
    }


@router.get("/summary")
async def growth_summary(_: GrowthViewer, db: DbSession) -> dict[str, Any]:
    async def count(model: Any, *conditions: Any) -> int:
        return int(await db.scalar(select(func.count(model.id)).where(*conditions)) or 0)

    return success(
        {
            "active_ads": await count(AdPlacement, AdPlacement.active.is_(True)),
            "ad_impressions": await count(AdEvent, AdEvent.event_type == "impression"),
            "ad_completions": await count(AdEvent, AdEvent.event_type == "completed"),
            "daily_claims": await count(DailyRewardClaim),
            "qualified_referrals": await count(Referral, Referral.status == "qualified"),
            "active_watch_parties": await count(WatchParty, WatchParty.status != "ended"),
            "growth_events": await count(GrowthEvent),
        }
    )


@router.get("/ads")
async def ads(_: GrowthViewer, db: DbSession) -> dict[str, Any]:
    rows = list((await db.scalars(select(AdPlacement).order_by(AdPlacement.priority.desc()))).all())
    return success([ad_data(row) for row in rows])


@router.post("/ads", status_code=status.HTTP_201_CREATED)
async def create_ad(
    payload: AdPlacementInput, request: Request, admin: GrowthManager, db: DbSession
) -> dict[str, Any]:
    if await db.scalar(select(AdPlacement.id).where(AdPlacement.key == payload.key)):
        raise AppError("AD_KEY_EXISTS", "An ad with this key already exists.", status_code=409)
    row = AdPlacement(**payload.model_dump(), countries=[], languages=[])
    db.add(row)
    await db.flush()
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="growth.ad.create",
        entity_type="ad_placement",
        entity_id=str(row.id),
        old_value=None,
        new_value=jsonable_encoder(ad_data(row)),
    )
    await db.commit()
    await db.refresh(row)
    return success(ad_data(row))


@router.get("/automations")
async def automations(_: GrowthViewer, db: DbSession) -> dict[str, Any]:
    rows = list((await db.scalars(select(GrowthAutomation).order_by(GrowthAutomation.name))).all())
    return success([automation_data(row) for row in rows])


@router.patch("/automations/{automation_id}")
async def update_automation(
    automation_id: UUID,
    payload: GrowthAutomationUpdate,
    request: Request,
    admin: GrowthManager,
    db: DbSession,
) -> dict[str, Any]:
    row = await db.get(GrowthAutomation, automation_id)
    if row is None:
        raise AppError("NOT_FOUND", "Growth automation not found.", status_code=404)
    old = automation_data(row)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="growth.automation.update",
        entity_type="growth_automation",
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(automation_data(row)),
    )
    await db.commit()
    await db.refresh(row)
    return success(automation_data(row))
