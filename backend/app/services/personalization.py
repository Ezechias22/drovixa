from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext
from app.core.exceptions import AppError
from app.core.security import hash_password, verify_password
from app.integrations.videos.base import VideoProvider
from app.models.base import utcnow
from app.models.content import Content, Episode
from app.models.enums import AgeRating, ContentStatus, ContentType, ContentVisibility, VideoStatus
from app.models.personalization import CastSession, ContentRating, DownloadLicense, ViewerProfile
from app.models.streaming import PlaybackSession
from app.schemas.personalization import ProfileCreate, ProfileUpdate
from app.services.monetization import has_active_subscription
from app.services.streaming import (
    _check_access,
    _check_rights,
    _episode_target,
    _movie_target,
    _request_country,
)

PROFILE_LIMIT = 5
DOWNLOAD_TTL = timedelta(hours=48)
AGE_VALUES = {
    AgeRating.ALL: 0,
    AgeRating.SEVEN_PLUS: 7,
    AgeRating.THIRTEEN_PLUS: 13,
    AgeRating.SIXTEEN_PLUS: 16,
    AgeRating.EIGHTEEN_PLUS: 18,
}


def profile_data(row: ViewerProfile) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "avatar_key": row.avatar_key,
        "is_kids": row.is_kids,
        "age_limit": row.age_limit,
        "language_code": row.language_code,
        "autoplay_next": row.autoplay_next,
        "autoplay_previews": row.autoplay_previews,
        "pin_protected": row.pin_hash is not None,
        "is_default": row.is_default,
        "active": row.active,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


async def ensure_default_profile(db: AsyncSession, context: AuthContext) -> ViewerProfile:
    row = await db.scalar(
        select(ViewerProfile)
        .where(ViewerProfile.user_id == context.user.id, ViewerProfile.active.is_(True))
        .order_by(ViewerProfile.is_default.desc(), ViewerProfile.created_at)
    )
    if row is not None:
        return row
    row = ViewerProfile(
        user_id=context.user.id,
        name=context.user.name.split()[0][:80] or "Profile",
        language_code=context.user.language_code or "en",
        is_default=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def owned_profile(
    db: AsyncSession,
    *,
    context: AuthContext,
    profile_id: UUID | None,
) -> ViewerProfile:
    if profile_id is None:
        return await ensure_default_profile(db, context)
    row = await db.scalar(
        select(ViewerProfile).where(
            ViewerProfile.id == profile_id,
            ViewerProfile.user_id == context.user.id,
            ViewerProfile.active.is_(True),
        )
    )
    if row is None:
        raise AppError("PROFILE_NOT_FOUND", "Viewer profile not found.", status_code=404)
    return row


async def list_profiles(db: AsyncSession, context: AuthContext) -> list[dict[str, Any]]:
    await ensure_default_profile(db, context)
    rows = list(
        (
            await db.scalars(
                select(ViewerProfile)
                .where(ViewerProfile.user_id == context.user.id, ViewerProfile.active.is_(True))
                .order_by(ViewerProfile.is_default.desc(), ViewerProfile.created_at)
            )
        ).all()
    )
    return [profile_data(row) for row in rows]


async def create_profile(
    db: AsyncSession, *, context: AuthContext, payload: ProfileCreate
) -> ViewerProfile:
    count = int(
        await db.scalar(
            select(func.count(ViewerProfile.id)).where(
                ViewerProfile.user_id == context.user.id, ViewerProfile.active.is_(True)
            )
        )
        or 0
    )
    if count >= PROFILE_LIMIT:
        raise AppError(
            "PROFILE_LIMIT_REACHED",
            f"An account can have up to {PROFILE_LIMIT} active profiles.",
            status_code=409,
        )
    row = ViewerProfile(
        user_id=context.user.id,
        name=payload.name,
        avatar_key=payload.avatar_key,
        is_kids=payload.is_kids,
        age_limit=min(payload.age_limit, 13) if payload.is_kids else payload.age_limit,
        language_code=payload.language_code.casefold(),
        autoplay_next=payload.autoplay_next,
        autoplay_previews=payload.autoplay_previews,
        pin_hash=hash_password(payload.pin) if payload.pin else None,
        is_default=count == 0,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_profile(
    db: AsyncSession,
    *,
    context: AuthContext,
    profile_id: UUID,
    payload: ProfileUpdate,
) -> ViewerProfile:
    row = await owned_profile(db, context=context, profile_id=profile_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"pin", "clear_pin"})
    for key, value in changes.items():
        if isinstance(value, str):
            value = value.strip()
        setattr(row, key, value)
    if row.is_kids and row.age_limit > 13:
        row.age_limit = 13
    if payload.clear_pin:
        row.pin_hash = None
    elif payload.pin:
        row.pin_hash = hash_password(payload.pin)
    await db.commit()
    await db.refresh(row)
    return row


async def delete_profile(db: AsyncSession, *, context: AuthContext, profile_id: UUID) -> None:
    row = await owned_profile(db, context=context, profile_id=profile_id)
    active_count = int(
        await db.scalar(
            select(func.count(ViewerProfile.id)).where(
                ViewerProfile.user_id == context.user.id, ViewerProfile.active.is_(True)
            )
        )
        or 0
    )
    if active_count <= 1 or row.is_default:
        raise AppError(
            "DEFAULT_PROFILE_REQUIRED",
            "The default or only profile cannot be deleted.",
            status_code=409,
        )
    row.active = False
    await db.execute(
        update(DownloadLicense)
        .where(DownloadLicense.profile_id == row.id, DownloadLicense.revoked_at.is_(None))
        .values(revoked_at=utcnow(), status="revoked")
    )
    await db.commit()


async def verify_profile_pin(
    db: AsyncSession,
    *,
    context: AuthContext,
    profile_id: UUID,
    pin: str,
) -> bool:
    row = await owned_profile(db, context=context, profile_id=profile_id)
    if row.pin_hash is None:
        return True
    return verify_password(pin, row.pin_hash)


def profile_allows_content(profile: ViewerProfile, content: Content) -> bool:
    if not profile.is_kids:
        return True
    return AGE_VALUES.get(content.age_rating, 18) <= profile.age_limit


def kids_age_ratings(profile: ViewerProfile | None) -> list[AgeRating] | None:
    if profile is None or not profile.is_kids:
        return None
    return [rating for rating, minimum in AGE_VALUES.items() if minimum <= profile.age_limit]


async def get_rating(
    db: AsyncSession, *, context: AuthContext, profile_id: UUID | None, content_id: UUID
) -> dict[str, Any]:
    profile = await owned_profile(db, context=context, profile_id=profile_id)
    row = await db.scalar(
        select(ContentRating).where(
            ContentRating.profile_id == profile.id, ContentRating.content_id == content_id
        )
    )
    content = await db.get(Content, content_id)
    if content is None:
        raise AppError("NOT_FOUND", "Content not found.", status_code=404)
    return {
        "content_id": content.id,
        "profile_id": profile.id,
        "score": row.score if row else None,
        "average": content.rating,
        "count": content.rating_count,
    }


async def rate_content(
    db: AsyncSession,
    *,
    context: AuthContext,
    profile_id: UUID | None,
    content_id: UUID,
    score: int,
) -> dict[str, Any]:
    profile = await owned_profile(db, context=context, profile_id=profile_id)
    content = await db.scalar(
        select(Content).where(
            Content.id == content_id,
            Content.deleted_at.is_(None),
            Content.status == ContentStatus.PUBLISHED,
            Content.visibility.in_([ContentVisibility.PUBLIC, ContentVisibility.UNLISTED]),
        )
    )
    if content is None:
        raise AppError("NOT_FOUND", "Content not found.", status_code=404)
    if not profile_allows_content(profile, content):
        raise AppError(
            "KIDS_PROFILE_RESTRICTED",
            "This title is not available for the selected Kids profile.",
            status_code=403,
        )
    row = await db.scalar(
        select(ContentRating).where(
            ContentRating.profile_id == profile.id, ContentRating.content_id == content.id
        )
    )
    if row is None:
        row = ContentRating(
            user_id=context.user.id,
            profile_id=profile.id,
            content_id=content.id,
            score=score,
        )
        db.add(row)
    else:
        row.score = score
    await db.flush()
    average, count = (
        await db.execute(
            select(func.avg(ContentRating.score), func.count(ContentRating.id)).where(
                ContentRating.content_id == content.id
            )
        )
    ).one()
    content.rating = (Decimal(str(average or 0)) * Decimal("2")).quantize(Decimal("0.01"))
    content.rating_count = int(count or 0)
    await db.commit()
    return await get_rating(db, context=context, profile_id=profile.id, content_id=content.id)


async def delete_rating(
    db: AsyncSession, *, context: AuthContext, profile_id: UUID | None, content_id: UUID
) -> dict[str, Any]:
    profile = await owned_profile(db, context=context, profile_id=profile_id)
    await db.execute(
        delete(ContentRating).where(
            ContentRating.profile_id == profile.id, ContentRating.content_id == content_id
        )
    )
    average, count = (
        await db.execute(
            select(func.avg(ContentRating.score), func.count(ContentRating.id)).where(
                ContentRating.content_id == content_id,
                ContentRating.profile_id != profile.id,
            )
        )
    ).one()
    content = await db.get(Content, content_id)
    if content:
        content.rating = (Decimal(str(average or 0)) * Decimal("2")).quantize(Decimal("0.01"))
        content.rating_count = int(count or 0)
    await db.commit()
    return await get_rating(db, context=context, profile_id=profile.id, content_id=content_id)


def _license_data(row: DownloadLicense) -> dict[str, Any]:
    return {
        "id": row.id,
        "profile_id": row.profile_id,
        "content_id": row.content_id,
        "episode_id": row.episode_id,
        "quality": row.quality,
        "status": row.status,
        "bytes_downloaded": row.bytes_downloaded,
        "expires_at": row.expires_at,
        "completed_at": row.completed_at,
        "revoked": row.revoked_at is not None,
    }


async def authorize_download(
    db: AsyncSession,
    *,
    provider: VideoProvider,
    request: Request,
    context: AuthContext,
    target_type: ContentType,
    target_id: UUID,
    profile_id: UUID | None,
    quality: str,
) -> dict[str, Any]:
    profile = await owned_profile(db, context=context, profile_id=profile_id)
    episode: Episode | None
    if target_type == ContentType.SERIES:
        content, episode, asset, access_type, free_from, free_until = await _episode_target(
            db, target_id
        )
    else:
        content, episode, asset, access_type, free_from, free_until = await _movie_target(
            db, target_id
        )
    _check_rights(content, _request_country(request))
    if not profile_allows_content(profile, content):
        raise AppError(
            "KIDS_PROFILE_RESTRICTED",
            "This title is not available for the selected Kids profile.",
            status_code=403,
        )
    await _check_access(
        db,
        context=context,
        content_id=content.id,
        episode_id=episode.id if episode else None,
        access_type=access_type,
        free_from=free_from,
        free_until=free_until,
    )
    premium = bool(
        {"premium_user", "super_admin"}.intersection(context.user.role_names)
    ) or await has_active_subscription(db, user_id=context.user.id)
    if not premium:
        raise AppError(
            "PREMIUM_REQUIRED",
            "Offline downloads are available to Premium members.",
            status_code=403,
        )
    if asset.status != VideoStatus.READY or asset.provider != provider.name:
        raise AppError("VIDEO_NOT_READY", "The video is not ready for download.", status_code=409)
    expires_at = utcnow() + DOWNLOAD_TTL
    grant = await provider.create_signed_download_url(
        provider_asset_id=asset.provider_asset_id,
        playback_id=asset.playback_id,
        expires_at=expires_at,
        quality=quality,
    )
    raw_token = secrets.token_urlsafe(48)
    row = DownloadLicense(
        user_id=context.user.id,
        profile_id=profile.id,
        device_id=context.session.device_id,
        content_id=content.id,
        episode_id=episode.id if episode else None,
        video_asset_id=asset.id,
        quality=grant.quality,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=grant.expires_at,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {
        **_license_data(row),
        "download_url": grant.url,
        "license_token": raw_token,
        "storage": "application_private",
    }


async def list_downloads(db: AsyncSession, *, context: AuthContext) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.scalars(
                select(DownloadLicense)
                .where(
                    DownloadLicense.user_id == context.user.id,
                    DownloadLicense.device_id == context.session.device_id,
                    DownloadLicense.status != "deleted",
                )
                .order_by(DownloadLicense.created_at.desc())
            )
        ).all()
    )
    return [_license_data(row) for row in rows]


async def update_download_status(
    db: AsyncSession,
    *,
    context: AuthContext,
    license_id: UUID,
    status: str,
    bytes_downloaded: int,
) -> dict[str, Any]:
    row = await db.scalar(
        select(DownloadLicense).where(
            DownloadLicense.id == license_id,
            DownloadLicense.user_id == context.user.id,
            DownloadLicense.device_id == context.session.device_id,
        )
    )
    if row is None:
        raise AppError("DOWNLOAD_NOT_FOUND", "Download license not found.", status_code=404)
    row.status = status
    row.bytes_downloaded = bytes_downloaded
    if status == "ready":
        row.completed_at = utcnow()
    if status == "deleted":
        row.revoked_at = utcnow()
    await db.commit()
    return _license_data(row)


async def verify_download(
    db: AsyncSession,
    *,
    context: AuthContext,
    license_id: UUID,
    raw_token: str,
) -> dict[str, Any]:
    row = await db.scalar(
        select(DownloadLicense).where(
            DownloadLicense.id == license_id,
            DownloadLicense.user_id == context.user.id,
            DownloadLicense.device_id == context.session.device_id,
        )
    )
    valid_token = row is not None and hmac.compare_digest(
        row.token_hash, hashlib.sha256(raw_token.encode()).hexdigest()
    )
    now = utcnow()
    valid = bool(
        row
        and valid_token
        and row.revoked_at is None
        and row.status in {"authorized", "downloading", "ready"}
        and (row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)) > now
    )
    if row and valid:
        row.last_verified_at = now
        await db.commit()
    return {"id": license_id, "valid": valid, "expires_at": row.expires_at if row else None}


async def start_cast_session(
    db: AsyncSession,
    *,
    context: AuthContext,
    profile_id: UUID | None,
    playback_session_id: UUID | None,
    target_device_id: str,
    target_device_name: str,
    target_type: str,
) -> CastSession:
    profile = await owned_profile(db, context=context, profile_id=profile_id)
    if playback_session_id:
        playback = await db.scalar(
            select(PlaybackSession.id).where(
                PlaybackSession.id == playback_session_id,
                PlaybackSession.user_id == context.user.id,
            )
        )
        if playback is None:
            raise AppError(
                "PLAYBACK_SESSION_INVALID", "Playback session is invalid.", status_code=403
            )
    now = utcnow()
    row = CastSession(
        user_id=context.user.id,
        profile_id=profile.id,
        device_id=context.session.device_id,
        playback_session_id=playback_session_id,
        target_device_id=target_device_id,
        target_device_name=target_device_name,
        target_type=target_type,
        status="connected",
        started_at=now,
        last_seen_at=now,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_cast_session(
    db: AsyncSession, *, context: AuthContext, cast_id: UUID, status: str
) -> CastSession:
    row = await db.scalar(
        select(CastSession).where(CastSession.id == cast_id, CastSession.user_id == context.user.id)
    )
    if row is None:
        raise AppError("CAST_SESSION_NOT_FOUND", "Cast session not found.", status_code=404)
    row.status = status
    row.last_seen_at = utcnow()
    if status == "ended":
        row.ended_at = row.last_seen_at
    await db.commit()
    return row


def cast_data(row: CastSession) -> dict[str, Any]:
    return {
        "id": row.id,
        "profile_id": row.profile_id,
        "playback_session_id": row.playback_session_id,
        "target_device_id": row.target_device_id,
        "target_device_name": row.target_device_name,
        "target_type": row.target_type,
        "status": row.status,
        "started_at": row.started_at,
        "last_seen_at": row.last_seen_at,
        "ended_at": row.ended_at,
    }
