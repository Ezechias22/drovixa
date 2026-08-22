from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentContext, DbSession
from app.models.notifications import PushToken
from app.schemas.common import success
from app.schemas.notifications import PushTokenRegistration
from app.services.notifications import (
    deactivate_device_push_tokens,
    deactivate_push_token,
    push_provider_status,
    push_token_data,
    register_push_token,
)

router = APIRouter(tags=["Push notifications"])


@router.get("/push/config")
async def push_config() -> dict[str, Any]:
    status_data = push_provider_status()
    return success(
        {
            "enabled": status_data["configured"],
            "provider": status_data["provider"],
            "project_id": status_data["project_id"],
        }
    )


@router.post("/push-tokens", status_code=status.HTTP_201_CREATED)
async def create_push_token(
    payload: PushTokenRegistration, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    row = await register_push_token(
        db,
        user_id=context.user.id,
        device_id=context.session.device.device_id,
        payload=payload,
    )
    return success(push_token_data(row))


@router.get("/push-tokens")
async def push_tokens(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    rows = list(
        await db.scalars(
            select(PushToken)
            .where(PushToken.user_id == context.user.id)
            .order_by(PushToken.updated_at.desc())
        )
    )
    return success([push_token_data(row) for row in rows])


@router.delete("/push-tokens/current")
async def delete_current_push_tokens(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    count = await deactivate_device_push_tokens(
        db,
        user_id=context.user.id,
        device_id=context.session.device.device_id,
    )
    return success({"deactivated": count})


@router.delete("/push-tokens/{push_token_id}")
async def delete_push_token(
    push_token_id: UUID, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    row = await deactivate_push_token(
        db, user_id=context.user.id, push_token_id=push_token_id
    )
    return success({"id": row.id, "active": row.active, "disabled_at": row.disabled_at})
