from typing import Annotated, Any

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import DbSession, require_permission
from app.core.exceptions import AppError
from app.models.configuration import FeatureFlag, RemoteConfig
from app.models.user import User
from app.schemas.common import success
from app.schemas.configuration import FeatureFlagUpdate, RemoteConfigUpdate
from app.services.audit import add_audit_log
from app.services.configuration import invalidate_runtime_configuration

router = APIRouter(prefix="/admin", tags=["Admin configuration"])
SettingsViewer = Annotated[User, require_permission("settings.view")]
SettingsManager = Annotated[User, require_permission("settings.manage")]


@router.get("/feature-flags")
async def admin_feature_flags(_: SettingsViewer, db: DbSession) -> dict[str, Any]:
    rows = (await db.scalars(select(FeatureFlag).order_by(FeatureFlag.key))).all()
    return success(
        [
            {
                "key": row.key,
                "description": row.description,
                "enabled": row.enabled,
                "rollout_percentage": row.rollout_percentage,
                "rules": row.rules,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]
    )


@router.patch("/feature-flags/{key}")
async def update_feature_flag(
    key: str,
    payload: FeatureFlagUpdate,
    request: Request,
    admin: SettingsManager,
    db: DbSession,
) -> dict[str, Any]:
    row = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == key).with_for_update())
    if row is None:
        raise AppError("NOT_FOUND", "The feature flag was not found.", status_code=404)
    old = {
        "enabled": row.enabled,
        "rollout_percentage": row.rollout_percentage,
        "rules": dict(row.rules),
    }
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(row, field, value)
    new = {
        "enabled": row.enabled,
        "rollout_percentage": row.rollout_percentage,
        "rules": dict(row.rules),
    }
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="feature_flag.update",
        entity_type="feature_flag",
        entity_id=str(row.id),
        old_value=old,
        new_value=new,
    )
    await db.commit()
    await invalidate_runtime_configuration()
    return success({"key": row.key, **new})


@router.get("/remote-config")
async def admin_remote_config(_: SettingsViewer, db: DbSession) -> dict[str, Any]:
    rows = (await db.scalars(select(RemoteConfig).order_by(RemoteConfig.key))).all()
    return success(
        [
            {
                "key": row.key,
                "value": row.value,
                "description": row.description,
                "is_public": row.is_public,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]
    )


@router.patch("/remote-config/{key}")
async def update_remote_config(
    key: str,
    payload: RemoteConfigUpdate,
    request: Request,
    admin: SettingsManager,
    db: DbSession,
) -> dict[str, Any]:
    row = await db.scalar(select(RemoteConfig).where(RemoteConfig.key == key).with_for_update())
    if row is None:
        raise AppError("NOT_FOUND", "The remote configuration key was not found.", status_code=404)
    old = {"value": row.value, "is_public": row.is_public}
    row.value = payload.value
    if payload.is_public is not None:
        row.is_public = payload.is_public
    new = {"value": row.value, "is_public": row.is_public}
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="remote_config.update",
        entity_type="remote_config",
        entity_id=str(row.id),
        old_value=old,
        new_value=new,
    )
    await db.commit()
    await invalidate_runtime_configuration()
    return success({"key": row.key, **new})
