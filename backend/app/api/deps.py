from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, cast

import jwt
from fastapi import Depends
from fastapi.params import Depends as DependsParam
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.models.auth import UserSession
from app.models.configuration import FeatureFlag
from app.models.enums import UserStatus
from app.models.rbac import Role
from app.models.user import User

DbSession = Annotated[AsyncSession, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: User
    session: UserSession


async def get_auth_context(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthContext:
    context = await _resolve_auth_context(db, credentials)
    if context is None:
        raise AppError("UNAUTHORIZED", "Authentication is required.", status_code=401)
    return context


async def get_optional_auth_context(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthContext | None:
    return await _resolve_auth_context(db, credentials)


async def _resolve_auth_context(
    db: AsyncSession,
    credentials: HTTPAuthorizationCredentials | None,
) -> AuthContext | None:
    if credentials is None:
        return None
    if credentials.scheme.casefold() != "bearer":
        raise AppError("UNAUTHORIZED", "Authentication is required.", status_code=401)
    try:
        claims = decode_access_token(credentials.credentials)
    except (jwt.PyJWTError, ValueError):
        raise AppError(
            "UNAUTHORIZED", "The access token is invalid or expired.", status_code=401
        ) from None
    session = await db.scalar(
        select(UserSession)
        .where(
            UserSession.id == claims.session_id,
            UserSession.user_id == claims.user_id,
            UserSession.revoked_at.is_(None),
        )
        .options(
            joinedload(UserSession.device),
            joinedload(UserSession.user).selectinload(User.roles).selectinload(Role.permissions),
        )
    )
    if session is None:
        raise AppError("SESSION_REVOKED", "This session is no longer active.", status_code=401)
    user = session.user
    if user.deleted_at is not None or user.status != UserStatus.ACTIVE:
        code = "ACCOUNT_SUSPENDED" if user.status == UserStatus.SUSPENDED else "FORBIDDEN"
        raise AppError(code, "This account cannot access the service.", status_code=403)
    return AuthContext(user=user, session=session)


CurrentContext = Annotated[AuthContext, Depends(get_auth_context)]
OptionalContext = Annotated[AuthContext | None, Depends(get_optional_auth_context)]


def require_permission(permission: str) -> DependsParam:
    async def dependency(context: CurrentContext) -> User:
        if permission not in context.user.permission_codes:
            raise AppError(
                "FORBIDDEN", "You do not have permission for this action.", status_code=403
            )
        return context.user

    return cast(DependsParam, Depends(dependency))


def require_feature_enabled(feature_key: str, *, error_code: str) -> DependsParam:
    async def dependency(db: DbSession) -> None:
        flag = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == feature_key))
        if flag is None or not flag.enabled or flag.rollout_percentage <= 0:
            raise AppError(
                error_code,
                "This feature is currently unavailable.",
                status_code=403,
            )

    return cast(DependsParam, Depends(dependency))
