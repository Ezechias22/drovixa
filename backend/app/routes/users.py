from typing import Any
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentContext, DbSession
from app.core.exceptions import AppError
from app.models.auth import Device, UserSession
from app.schemas.common import success
from app.schemas.user import DeviceOut, UserOut, UserUpdateInput
from app.services.auth import revoke_session

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me")
async def me(context: CurrentContext) -> dict[str, Any]:
    return success(UserOut.from_user(context.user))


@router.patch("/me")
async def update_me(
    payload: UserUpdateInput, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(context.user, key, value.strip() if isinstance(value, str) else value)
    await db.commit()
    return success(UserOut.from_user(context.user))


@router.get("/me/devices")
async def list_devices(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    devices = (
        await db.scalars(
            select(Device)
            .where(Device.user_id == context.user.id)
            .order_by(Device.last_seen_at.desc())
        )
    ).all()
    data = [
        DeviceOut(
            id=device.id,
            device_id=device.device_id,
            name=device.name,
            platform=device.platform,
            last_ip=device.last_ip,
            last_seen_at=device.last_seen_at,
            current=device.id == context.session.device_id,
        )
        for device in devices
    ]
    return success(data)


@router.delete("/me/devices/{device_id}")
async def logout_device(device_id: UUID, context: CurrentContext, db: DbSession) -> dict[str, Any]:
    device = await db.scalar(
        select(Device).where(Device.id == device_id, Device.user_id == context.user.id)
    )
    if device is None:
        raise AppError("NOT_FOUND", "The device was not found.", status_code=404)
    session_ids = (
        await db.scalars(
            select(UserSession.id).where(
                UserSession.device_id == device.id,
                UserSession.user_id == context.user.id,
                UserSession.revoked_at.is_(None),
            )
        )
    ).all()
    for session_id in session_ids:
        await revoke_session(db, session_id, reason="device_logout")
    await db.commit()
    return success({"device_id": device.id, "logged_out": True})
