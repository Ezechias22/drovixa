from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select

from app.api.deps import DbSession, require_permission
from app.core.exceptions import AppError
from app.models.configuration import FeatureFlag, RemoteConfig
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
from app.schemas.growth import AdPlacementInput, EngagementConfigUpdate, GrowthAutomationUpdate
from app.services.audit import add_audit_log
from app.services.configuration import invalidate_runtime_configuration
from app.services.engagement import DEFAULT_PREMIUM_CONFIG, DEFAULT_REWARDED_CONFIG

router = APIRouter(prefix="/admin/growth", tags=["Admin growth"])
GrowthViewer = Annotated[User, require_permission("analytics.view")]
GrowthManager = Annotated[User, require_permission("settings.manage")]

ENGAGEMENT_FLAG_KEYS = (
    "rewarded_ads_enabled",
    "premium_offers_enabled",
    "content_notifications_enabled",
    "continue_watching_reminders_enabled",
)


async def engagement_admin_data(db: DbSession) -> dict[str, Any]:
    flags = {
        row.key: row.enabled
        for row in await db.scalars(
            select(FeatureFlag).where(FeatureFlag.key.in_(ENGAGEMENT_FLAG_KEYS))
        )
    }
    config_rows = {
        row.key: row.value
        for row in await db.scalars(
            select(RemoteConfig).where(
                RemoteConfig.key.in_(("admob_rewarded", "premium_engagement"))
            )
        )
    }
    rewarded = {**DEFAULT_REWARDED_CONFIG, **config_rows.get("admob_rewarded", {})}
    premium = {**DEFAULT_PREMIUM_CONFIG, **config_rows.get("premium_engagement", {})}
    return {
        **{key: bool(flags.get(key, False)) for key in ENGAGEMENT_FLAG_KEYS},
        "coins_per_ad": int(rewarded["coins_per_ad"]),
        "daily_limit": int(rewarded["daily_limit"]),
        "max_per_session": int(premium["max_per_session"]),
        "max_per_day": int(premium["max_per_day"]),
        "first_delay_seconds": int(premium["first_delay_seconds"]),
        "repeat_delay_seconds": int(premium["repeat_delay_seconds"]),
        "premium_notification_cooldown_hours": int(
            premium["notification_cooldown_hours"]
        ),
        "continue_after_hours": int(premium["continue_after_hours"]),
        "continue_cooldown_hours": int(premium["continue_cooldown_hours"]),
    }


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


@router.get("/config")
async def engagement_configuration(_: GrowthViewer, db: DbSession) -> dict[str, Any]:
    return success(await engagement_admin_data(db))


@router.patch("/config")
async def update_engagement_configuration(
    payload: EngagementConfigUpdate,
    request: Request,
    admin: GrowthManager,
    db: DbSession,
) -> dict[str, Any]:
    old = await engagement_admin_data(db)
    changes = payload.model_dump()
    flags = list(
        await db.scalars(
            select(FeatureFlag)
            .where(FeatureFlag.key.in_(ENGAGEMENT_FLAG_KEYS))
            .with_for_update()
        )
    )
    if len(flags) != len(ENGAGEMENT_FLAG_KEYS):
        raise AppError(
            "ENGAGEMENT_CONFIG_INCOMPLETE",
            "Run the latest database migration before updating engagement settings.",
            status_code=409,
        )
    for row in flags:
        row.enabled = bool(changes[row.key])
        row.rollout_percentage = 100

    configs = {
        row.key: row
        for row in await db.scalars(
            select(RemoteConfig)
            .where(RemoteConfig.key.in_(("admob_rewarded", "premium_engagement")))
            .with_for_update()
        )
    }
    if set(configs) != {"admob_rewarded", "premium_engagement"}:
        raise AppError(
            "ENGAGEMENT_CONFIG_INCOMPLETE",
            "Run the latest database migration before updating engagement settings.",
            status_code=409,
        )
    configs["admob_rewarded"].value = {
        "coins_per_ad": changes["coins_per_ad"],
        "daily_limit": changes["daily_limit"],
    }
    configs["premium_engagement"].value = {
        "max_per_session": changes["max_per_session"],
        "max_per_day": changes["max_per_day"],
        "first_delay_seconds": changes["first_delay_seconds"],
        "repeat_delay_seconds": changes["repeat_delay_seconds"],
        "notification_cooldown_hours": changes[
            "premium_notification_cooldown_hours"
        ],
        "continue_after_hours": changes["continue_after_hours"],
        "continue_cooldown_hours": changes["continue_cooldown_hours"],
    }
    premium_automation = await db.scalar(
        select(GrowthAutomation)
        .where(GrowthAutomation.key == "premium-offer-notification")
        .with_for_update()
    )
    if premium_automation:
        premium_automation.cooldown_hours = changes[
            "premium_notification_cooldown_hours"
        ]
    new = await engagement_admin_data(db)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="growth.engagement_config.update",
        entity_type="engagement_config",
        entity_id="phase13",
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(new),
    )
    await db.commit()
    await invalidate_runtime_configuration()
    return success(new)


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
