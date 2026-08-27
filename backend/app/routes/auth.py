from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.api.deps import CurrentContext, DbSession, require_feature_enabled
from app.core.network import forwarded_for
from app.core.rate_limit import rate_limit
from app.schemas.auth import ChangePasswordInput, LoginInput, RefreshInput, RegisterInput
from app.schemas.common import success
from app.schemas.user import UserOut
from app.services.auth import (
    IssuedTokens,
    change_user_password,
    login_user,
    register_user,
    revoke_all_user_sessions,
    revoke_session,
    rotate_refresh_token,
)
from app.services.notifications import deactivate_device_push_tokens, disable_user_push_tokens

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _token_response(issued: IssuedTokens) -> dict[str, Any]:
    return success(
        {
            "access_token": issued.access_token,
            "refresh_token": issued.refresh_token,
            "token_type": "bearer",
            "expires_in": issued.expires_in,
            "user": UserOut.from_user(issued.user),
        }
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        require_feature_enabled("registration_enabled", error_code="REGISTRATION_DISABLED"),
        Depends(rate_limit("register", requests=5, window_seconds=3600)),
    ],
)
async def register(payload: RegisterInput, request: Request, db: DbSession) -> dict[str, Any]:
    issued = await register_user(
        db,
        payload,
        forwarded_for=forwarded_for(request),
        direct_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    return _token_response(issued)


@router.post(
    "/login",
    dependencies=[Depends(rate_limit("login", requests=10, window_seconds=900))],
)
async def login(payload: LoginInput, request: Request, db: DbSession) -> dict[str, Any]:
    issued = await login_user(
        db,
        payload,
        forwarded_for=forwarded_for(request),
        direct_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    return _token_response(issued)


@router.post(
    "/refresh",
    dependencies=[Depends(rate_limit("refresh", requests=30, window_seconds=900))],
)
async def refresh(payload: RefreshInput, db: DbSession) -> dict[str, Any]:
    return _token_response(await rotate_refresh_token(db, payload.refresh_token))


@router.post("/logout")
async def logout(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    await deactivate_device_push_tokens(
        db,
        user_id=context.user.id,
        device_id=context.session.device.device_id,
        commit=False,
    )
    await revoke_session(db, context.session.id, reason="user_logout")
    await db.commit()
    return success({"logged_out": True})


@router.post("/logout-all")
async def logout_all(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    await disable_user_push_tokens(db, user_id=context.user.id, commit=False)
    await revoke_all_user_sessions(db, context.user.id, reason="user_logout_all")
    await db.commit()
    return success({"logged_out": True, "all_devices": True})


@router.post(
    "/change-password",
    dependencies=[Depends(rate_limit("change-password", requests=5, window_seconds=900))],
)
async def change_password(
    payload: ChangePasswordInput,
    context: CurrentContext,
    db: DbSession,
) -> dict[str, Any]:
    await change_user_password(db, context.user, payload)
    return success({"password_changed": True})
