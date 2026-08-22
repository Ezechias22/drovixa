from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    normalize_email,
    utcnow,
    verify_password,
)
from app.models.auth import Device, RefreshToken, UserSession
from app.models.enums import UserStatus
from app.models.monetization import Wallet
from app.models.rbac import Role
from app.models.user import User
from app.repositories.users import get_role_by_name, get_user_by_email
from app.schemas.auth import DeviceInput, LoginInput, RegisterInput


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    user: User


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _client_ip(forwarded_for: str | None, direct_ip: str | None) -> str | None:
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()[:64]
    return direct_ip[:64] if direct_ip else None


async def register_user(
    db: AsyncSession,
    payload: RegisterInput,
    *,
    forwarded_for: str | None,
    direct_ip: str | None,
    user_agent: str | None,
) -> IssuedTokens:
    email = normalize_email(str(payload.email))
    if await get_user_by_email(db, email):
        raise AppError(
            "EMAIL_ALREADY_REGISTERED",
            "An account already uses this email.",
            status_code=409,
        )
    role = await get_role_by_name(db, "user")
    if role is None:
        raise AppError(
            "SERVICE_MISCONFIGURED",
            "Required system roles are missing.",
            status_code=500,
        )
    user = User(
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
    )
    user.roles.append(role)
    db.add(user)
    try:
        await db.flush()
        db.add(Wallet(user_id=user.id))
        issued = await _create_session_and_tokens(
            db,
            user,
            payload.device,
            ip=_client_ip(forwarded_for, direct_ip),
            user_agent=user_agent,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise AppError(
            "EMAIL_ALREADY_REGISTERED",
            "An account already uses this email.",
            status_code=409,
        ) from exc
    return issued


async def login_user(
    db: AsyncSession,
    payload: LoginInput,
    *,
    forwarded_for: str | None,
    direct_ip: str | None,
    user_agent: str | None,
) -> IssuedTokens:
    user = await get_user_by_email(db, normalize_email(str(payload.email)))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AppError("INVALID_CREDENTIALS", "Email or password is incorrect.", status_code=401)
    if user.deleted_at is not None or user.status == UserStatus.DELETED:
        raise AppError("ACCOUNT_DELETED", "This account is no longer available.", status_code=403)
    if user.status == UserStatus.SUSPENDED:
        raise AppError("ACCOUNT_SUSPENDED", "This account is suspended.", status_code=403)
    if user.status == UserStatus.BANNED:
        raise AppError("ACCOUNT_BANNED", "This account is banned.", status_code=403)
    issued = await _create_session_and_tokens(
        db,
        user,
        payload.device,
        ip=_client_ip(forwarded_for, direct_ip),
        user_agent=user_agent,
    )
    await db.commit()
    return issued


async def _create_session_and_tokens(
    db: AsyncSession,
    user: User,
    device_input: DeviceInput,
    *,
    ip: str | None,
    user_agent: str | None,
) -> IssuedTokens:
    now = utcnow()
    device = await db.scalar(
        select(Device).where(
            Device.user_id == user.id,
            Device.device_id == device_input.device_id,
        )
    )
    if device is None:
        device = Device(
            user_id=user.id,
            device_id=device_input.device_id,
            name=device_input.name,
            platform=device_input.platform,
            last_ip=ip,
            last_seen_at=now,
        )
        db.add(device)
        await db.flush()
    else:
        device.name = device_input.name
        device.platform = device_input.platform
        device.last_ip = ip
        device.last_seen_at = now

    session = UserSession(
        user_id=user.id,
        device_id=device.id,
        last_seen_at=now,
        created_ip=ip,
        user_agent=user_agent[:1000] if user_agent else None,
    )
    db.add(session)
    await db.flush()
    return await _issue_tokens(db, user=user, session=session, family_id=uuid4())


async def _issue_tokens(
    db: AsyncSession, *, user: User, session: UserSession, family_id: UUID
) -> IssuedTokens:
    raw_refresh, refresh_hash = create_refresh_token()
    refresh = RefreshToken(
        user_id=user.id,
        session_id=session.id,
        family_id=family_id,
        token_hash=refresh_hash,
        expires_at=utcnow() + timedelta(days=get_settings().REFRESH_TOKEN_DAYS),
    )
    db.add(refresh)
    await db.flush()
    access, expires_in = create_access_token(user_id=user.id, session_id=session.id)
    return IssuedTokens(access, raw_refresh, expires_in, user)


async def rotate_refresh_token(db: AsyncSession, raw_token: str) -> IssuedTokens:
    token_hash = hash_refresh_token(raw_token)
    token = await db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
        .options(
            joinedload(RefreshToken.session)
            .selectinload(UserSession.user)
            .selectinload(User.roles)
            .selectinload(Role.permissions)
        )
    )
    if token is None:
        raise AppError("INVALID_REFRESH_TOKEN", "The refresh token is invalid.", status_code=401)
    now = utcnow()
    if token.revoked_at is not None:
        await _revoke_family(db, token.family_id, reason="refresh_token_reuse")
        token.reuse_detected_at = now
        await db.commit()
        raise AppError(
            "REFRESH_TOKEN_REUSED",
            "This session was revoked because a refresh token was reused.",
            status_code=401,
        )
    session = token.session
    if session.revoked_at is not None:
        raise AppError("SESSION_REVOKED", "This session has been revoked.", status_code=401)
    if _aware(token.expires_at) <= now:
        token.revoked_at = now
        await db.commit()
        raise AppError("REFRESH_TOKEN_EXPIRED", "The refresh token has expired.", status_code=401)
    user = session.user
    if user.status != UserStatus.ACTIVE or user.deleted_at is not None:
        await revoke_session(db, session.id, reason="account_unavailable")
        await db.commit()
        raise AppError("ACCOUNT_UNAVAILABLE", "This account cannot sign in.", status_code=403)

    issued = await _issue_tokens(db, user=user, session=session, family_id=token.family_id)
    replacement = await db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(issued.refresh_token)
        )
    )
    if replacement is None:
        raise RuntimeError("Refresh token persistence invariant failed")
    token.revoked_at = now
    token.replaced_by_token_id = replacement.id
    session.last_seen_at = now
    session.device.last_seen_at = now
    await db.commit()
    return issued


async def _revoke_family(db: AsyncSession, family_id: UUID, *, reason: str) -> None:
    now = utcnow()
    session_ids = select(RefreshToken.session_id).where(RefreshToken.family_id == family_id)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await db.execute(
        update(UserSession)
        .where(UserSession.id.in_(session_ids), UserSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason=reason)
    )


async def revoke_session(db: AsyncSession, session_id: UUID, *, reason: str) -> None:
    now = utcnow()
    await db.execute(
        update(UserSession)
        .where(UserSession.id == session_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason=reason)
    )
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.session_id == session_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def revoke_all_user_sessions(db: AsyncSession, user_id: UUID, *, reason: str) -> None:
    now = utcnow()
    await db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now, revoke_reason=reason)
    )
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
