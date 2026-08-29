import base64
import binascii
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import CurrentContext, DbSession
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models.auth import Device, UserSession
from app.models.base import utcnow
from app.models.user import UserAvatar
from app.schemas.common import success
from app.schemas.user import AvatarUploadInput, DeviceOut, UserOut, UserUpdateInput
from app.services.auth import revoke_session

router = APIRouter(prefix="/users", tags=["Users"])
MAX_AVATAR_BYTES = 1_800_000


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


@router.post("/me/avatar")
async def upload_avatar(
    payload: AvatarUploadInput, request: Request, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    try:
        image_data = base64.b64decode(payload.base64_data, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise AppError(
            "VALIDATION_ERROR", "The profile photo is invalid.", status_code=422
        ) from exc
    if not image_data or len(image_data) > MAX_AVATAR_BYTES:
        raise AppError(
            "VALIDATION_ERROR",
            "The profile photo must be smaller than 1.8 MB.",
            status_code=422,
        )
    avatar = await db.get(UserAvatar, context.user.id)
    if avatar is None:
        avatar = UserAvatar(
            user_id=context.user.id,
            mime_type=payload.mime_type,
            image_data=image_data,
        )
        db.add(avatar)
    else:
        avatar.mime_type = payload.mime_type
        avatar.image_data = image_data
    version = int(utcnow().timestamp())
    origin = str(request.base_url).rstrip("/")
    context.user.avatar_url = (
        f"{origin}{get_settings().API_V1_PREFIX}/media/users/"
        f"{context.user.id}/avatar?v={version}"
    )
    await db.commit()
    return success(UserOut.from_user(context.user))


@router.delete("/me/avatar")
async def delete_avatar(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    avatar = await db.get(UserAvatar, context.user.id)
    if avatar is not None:
        await db.delete(avatar)
    context.user.avatar_url = None
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
