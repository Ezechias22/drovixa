from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from fastapi import Request
from sqlalchemy import distinct, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.api.deps import AuthContext
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.localization import localized_fields
from app.core.network import client_ip
from app.integrations.videos.base import VideoProvider
from app.integrations.videos.factory import (
    get_original_video_provider,
)
from app.models.base import utcnow
from app.models.configuration import FeatureFlag
from app.models.content import Content, Episode, Movie, Series, Subtitle, VideoAsset
from app.models.enums import (
    ContentStatus,
    ContentType,
    ContentVisibility,
    EpisodeAccessType,
    VideoStatus,
)
from app.models.experience import Favorite
from app.models.streaming import (
    PlaybackSession,
    UserEntitlement,
    WatchHistory,
    WatchProgress,
)
from app.services.content import content_data, episode_data
from app.services.monetization import has_active_subscription


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _request_country(request: Request) -> str | None:
    value = request.headers.get(get_settings().GEO_COUNTRY_HEADER)
    if not value or len(value.strip()) != 2:
        return None
    return value.strip().upper()


def _request_ip(request: Request) -> str | None:
    return client_ip(request)


def _check_rights(content: Content, country: str | None) -> None:
    now = utcnow()
    if content.status != ContentStatus.PUBLISHED or content.deleted_at is not None:
        raise AppError("CONTENT_NOT_AVAILABLE", "This content is not available.", status_code=403)
    if content.visibility not in {ContentVisibility.PUBLIC, ContentVisibility.UNLISTED}:
        raise AppError("CONTENT_NOT_AVAILABLE", "This content is not available.", status_code=403)
    if content.published_at and _aware(content.published_at) > now:
        raise AppError(
            "CONTENT_NOT_AVAILABLE", "This content is not available yet.", status_code=403
        )
    if content.license_start and _aware(content.license_start) > now:
        raise AppError(
            "CONTENT_NOT_AVAILABLE", "The content license is not active.", status_code=403
        )
    if content.license_end and _aware(content.license_end) <= now:
        raise AppError("CONTENT_NOT_AVAILABLE", "The content license has expired.", status_code=403)
    allowed = {item.upper() for item in content.allowed_countries}
    blocked = {item.upper() for item in content.blocked_countries}
    if allowed and (country is None or country not in allowed):
        raise AppError("GEO_BLOCKED", "Content unavailable in your region.", status_code=403)
    if country and country in blocked:
        raise AppError("GEO_BLOCKED", "Content unavailable in your region.", status_code=403)


async def _guest_enabled(db: AsyncSession) -> bool:
    flag = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == "guest_mode_enabled"))
    return bool(flag and flag.enabled and flag.rollout_percentage > 0)


def _scheduled_free(
    access_type: EpisodeAccessType, start: datetime | None, end: datetime | None
) -> bool:
    if access_type != EpisodeAccessType.SCHEDULED_FREE:
        return False
    now = utcnow()
    return (start is None or _aware(start) <= now) and (end is None or _aware(end) > now)


async def _has_entitlement(
    db: AsyncSession,
    *,
    user_id: UUID,
    content_id: UUID,
    episode_id: UUID | None,
) -> bool:
    now = utcnow()
    return (
        await db.scalar(
            select(UserEntitlement.id).where(
                UserEntitlement.user_id == user_id,
                UserEntitlement.content_id == content_id,
                or_(
                    UserEntitlement.episode_id == episode_id,
                    UserEntitlement.episode_id.is_(None),
                ),
                or_(UserEntitlement.starts_at.is_(None), UserEntitlement.starts_at <= now),
                or_(
                    UserEntitlement.is_permanent.is_(True),
                    UserEntitlement.expires_at.is_(None),
                    UserEntitlement.expires_at > now,
                ),
            )
        )
        is not None
    )


async def _check_access(
    db: AsyncSession,
    *,
    context: AuthContext | None,
    content_id: UUID,
    episode_id: UUID | None,
    access_type: EpisodeAccessType,
    free_from: datetime | None = None,
    free_until: datetime | None = None,
) -> None:
    is_free = access_type == EpisodeAccessType.FREE or _scheduled_free(
        access_type, free_from, free_until
    )
    if is_free:
        if context is None and not await _guest_enabled(db):
            raise AppError("UNAUTHORIZED", "Authentication is required.", status_code=401)
        return
    if context is None:
        raise AppError("UNAUTHORIZED", "Login is required to watch this content.", status_code=401)
    premium = "premium_user" in context.user.role_names or await has_active_subscription(
        db, user_id=context.user.id
    )
    entitled = await _has_entitlement(
        db,
        user_id=context.user.id,
        content_id=content_id,
        episode_id=episode_id,
    )
    if access_type == EpisodeAccessType.PREMIUM_SUBSCRIPTION and not premium:
        raise AppError("PREMIUM_REQUIRED", "Premium is required for this content.", status_code=403)
    if access_type in {EpisodeAccessType.COIN_UNLOCK, EpisodeAccessType.AD_UNLOCK} and not entitled:
        raise AppError("CONTENT_LOCKED", "This content must be unlocked first.", status_code=403)
    if access_type == EpisodeAccessType.PREMIUM_OR_COIN and not (premium or entitled):
        raise AppError(
            "PREMIUM_REQUIRED",
            "Premium or an episode entitlement is required.",
            status_code=403,
        )
    if access_type == EpisodeAccessType.SCHEDULED_FREE and not (premium or entitled):
        raise AppError("CONTENT_NOT_AVAILABLE", "This episode is not free yet.", status_code=403)


async def _check_device_limit(db: AsyncSession, context: AuthContext) -> None:
    now = utcnow()
    current_device_id = context.session.device_id
    active_devices = await db.scalar(
        select(func.count(distinct(PlaybackSession.device_id))).where(
            PlaybackSession.user_id == context.user.id,
            PlaybackSession.device_id != current_device_id,
            PlaybackSession.expires_at > now,
            PlaybackSession.revoked_at.is_(None),
        )
    )
    premium = "premium_user" in context.user.role_names or await has_active_subscription(
        db, user_id=context.user.id
    )
    limit = (
        get_settings().PREMIUM_SIMULTANEOUS_STREAM_LIMIT
        if premium
        else get_settings().DEFAULT_SIMULTANEOUS_STREAM_LIMIT
    )
    if int(active_devices or 0) >= limit:
        raise AppError(
            "DEVICE_LIMIT_REACHED",
            "The simultaneous playback device limit has been reached.",
            status_code=403,
        )


async def _episode_target(
    db: AsyncSession, episode_id: UUID
) -> tuple[Content, Episode, VideoAsset, EpisodeAccessType, datetime | None, datetime | None]:
    episode = await db.scalar(
        select(Episode)
        .where(Episode.id == episode_id, Episode.deleted_at.is_(None))
        .options(
            joinedload(Episode.series).joinedload(Series.content),
            joinedload(Episode.video_asset)
            .selectinload(VideoAsset.subtitles)
            .selectinload(Subtitle.language),
        )
    )
    if episode is None or episode.status != ContentStatus.PUBLISHED:
        raise AppError("NOT_FOUND", "Episode not found.", status_code=404)
    if episode.published_at and _aware(episode.published_at) > utcnow():
        raise AppError(
            "CONTENT_NOT_AVAILABLE", "This episode is not available yet.", status_code=403
        )
    asset = episode.video_asset
    if asset is None or asset.deleted_at is not None:
        raise AppError("VIDEO_NOT_READY", "The episode video is unavailable.", status_code=409)
    return (
        episode.series.content,
        episode,
        asset,
        episode.access_type,
        episode.free_from,
        episode.free_until,
    )


async def _movie_target(
    db: AsyncSession, movie_id: UUID
) -> tuple[Content, None, VideoAsset, EpisodeAccessType, None, None]:
    movie = await db.scalar(
        select(Movie)
        .where(Movie.id == movie_id)
        .options(
            joinedload(Movie.content),
            joinedload(Movie.video_asset)
            .selectinload(VideoAsset.subtitles)
            .selectinload(Subtitle.language),
        )
    )
    if movie is None:
        raise AppError("NOT_FOUND", "Movie not found.", status_code=404)
    asset = movie.video_asset
    if asset is None or asset.deleted_at is not None:
        raise AppError("VIDEO_NOT_READY", "The movie video is unavailable.", status_code=409)
    return movie.content, None, asset, movie.access_type, None, None


async def authorize_playback(
    db: AsyncSession,
    *,
    provider: VideoProvider,
    request: Request,
    context: AuthContext | None,
    target_type: ContentType,
    target_id: UUID,
    client_device_id: str | None,
    profile_id: UUID | None = None,
) -> dict[str, Any]:
    content: Content
    episode: Episode | None
    asset: VideoAsset
    access_type: EpisodeAccessType
    free_from: datetime | None
    free_until: datetime | None
    if target_type == ContentType.SERIES:
        content, episode, asset, access_type, free_from, free_until = await _episode_target(
            db, target_id
        )
    else:
        content, episode, asset, access_type, free_from, free_until = await _movie_target(
            db, target_id
        )
    country = _request_country(request)
    _check_rights(content, country)
    profile = None
    if context is not None:
        # Local import avoids a module cycle: personalization reuses playback rights checks.
        from app.services.personalization import owned_profile, profile_allows_content

        profile = await owned_profile(db, context=context, profile_id=profile_id)
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
    if asset.status != VideoStatus.READY:
        raise AppError("VIDEO_NOT_READY", "The video is still processing.", status_code=409)
    bundled_providers = {"drovixa_original": get_original_video_provider}
    provider_factory = bundled_providers.get(asset.provider)
    effective_provider = provider_factory() if provider_factory else provider
    if asset.provider != effective_provider.name:
        raise AppError(
            "VIDEO_PROVIDER_UNAVAILABLE",
            "The provider for this video is unavailable.",
            status_code=503,
        )
    if context:
        await _check_device_limit(db, context)
        device_id = context.session.device_id
        effective_client_device_id = context.session.device.device_id
    else:
        if not client_device_id:
            raise AppError(
                "DEVICE_ID_REQUIRED",
                "A device identifier is required for guest playback.",
                status_code=422,
            )
        device_id = None
        effective_client_device_id = client_device_id
    expires_at = utcnow() + timedelta(seconds=get_settings().VIDEO_PLAYBACK_TOKEN_TTL_SECONDS)
    grant = await effective_provider.create_signed_url(
        provider_asset_id=asset.provider_asset_id,
        playback_id=asset.playback_id,
        expires_at=expires_at,
        country_code=country,
    )
    playback = PlaybackSession(
        user_id=context.user.id if context else None,
        auth_session_id=context.session.id if context else None,
        device_id=device_id,
        client_device_id=effective_client_device_id,
        content_id=content.id,
        episode_id=episode.id if episode else None,
        video_asset_id=asset.id,
        provider=effective_provider.name,
        country_code=country,
        ip=_request_ip(request),
        expires_at=grant.expires_at,
        last_activity_at=utcnow(),
    )
    db.add(playback)
    await db.flush()
    resume_position_seconds = 0
    is_favorite = False
    if context is not None:
        progress = await db.scalar(
            select(WatchProgress).where(
                WatchProgress.user_id == context.user.id,
                WatchProgress.content_id == content.id,
                WatchProgress.episode_id == (episode.id if episode else None),
            )
        )
        if progress is not None and not progress.completed:
            resume_position_seconds = max(0, progress.position_seconds)
        is_favorite = (
            await db.scalar(
                select(Favorite.id).where(
                    Favorite.user_id == context.user.id,
                    Favorite.content_id == content.id,
                )
            )
            is not None
        )
    previous_episode_id = None
    next_episode_id = None
    if episode is not None:
        published_episode = (
            Episode.series_id == episode.series_id,
            Episode.deleted_at.is_(None),
            Episode.status == ContentStatus.PUBLISHED,
            or_(Episode.published_at.is_(None), Episode.published_at <= utcnow()),
        )
        previous_episode_id = await db.scalar(
            select(Episode.id)
            .where(*published_episode, Episode.episode_number < episode.episode_number)
            .order_by(Episode.episode_number.desc())
            .limit(1)
        )
        next_episode_id = await db.scalar(
            select(Episode.id)
            .where(*published_episode, Episode.episode_number > episode.episode_number)
            .order_by(Episode.episode_number.asc())
            .limit(1)
        )
    await db.commit()
    subtitle_tracks = [
        {
            "id": subtitle.id,
            "language_code": subtitle.language.code,
            "label": subtitle.label,
            "format": subtitle.format,
            "url": subtitle.file_url,
            "is_default": subtitle.is_default,
        }
        for subtitle in asset.subtitles
        if subtitle.deleted_at is None
    ]
    localized_content_title = localized_fields(
        content.translations, {"title": content.title}
    )["title"]
    localized_playback_title = (
        localized_fields(episode.translations, {"title": episode.title})["title"]
        if episode
        else localized_content_title
    )
    return {
        "playback_session_id": playback.id,
        "content_type": target_type,
        "content_id": content.id,
        "episode_id": episode.id if episode else None,
        "hls_url": grant.hls_url,
        "dash_url": grant.dash_url,
        "expires_at": grant.expires_at,
        "duration_seconds": asset.duration_seconds,
        "width": asset.width,
        "height": asset.height,
        "aspect_ratio": asset.aspect_ratio,
        "orientation": episode.orientation if episode else (
            "vertical"
            if asset.width and asset.height and asset.height > asset.width
            else "horizontal"
        ),
        "title": localized_playback_title,
        "content_title": localized_content_title,
        "poster_url": episode.thumbnail_url if episode else content.poster_url,
        "profile_id": profile.id if profile else None,
        "autoplay_next": profile.autoplay_next if profile else True,
        "resume_position_seconds": resume_position_seconds,
        "previous_episode_id": previous_episode_id,
        "next_episode_id": next_episode_id,
        "is_favorite": is_favorite,
        "subtitles": subtitle_tracks,
        "progress_sync_interval_seconds": get_settings().PROGRESS_SYNC_INTERVAL_SECONDS,
    }


async def sync_progress(
    db: AsyncSession,
    *,
    context: AuthContext,
    playback_session_id: UUID,
    position_seconds: int,
    duration_seconds: int,
) -> dict[str, Any]:
    playback = await db.scalar(
        select(PlaybackSession)
        .where(
            PlaybackSession.id == playback_session_id,
            PlaybackSession.user_id == context.user.id,
            PlaybackSession.auth_session_id == context.session.id,
            PlaybackSession.revoked_at.is_(None),
        )
        .options(joinedload(PlaybackSession.content), joinedload(PlaybackSession.episode))
    )
    if playback is None:
        raise AppError("PLAYBACK_SESSION_INVALID", "Playback session is invalid.", status_code=403)
    if _aware(playback.expires_at) <= utcnow():
        raise AppError(
            "PLAYBACK_SESSION_EXPIRED", "Playback authorization expired.", status_code=401
        )
    position = min(position_seconds, duration_seconds)
    percentage_value = min(Decimal(position * 100) / Decimal(duration_seconds), Decimal(100))
    percentage = percentage_value.quantize(Decimal("0.01"))
    completed = percentage >= Decimal(get_settings().WATCH_COMPLETION_PERCENTAGE)
    progress = await db.scalar(
        select(WatchProgress).where(
            WatchProgress.user_id == context.user.id,
            WatchProgress.episode_id == playback.episode_id,
            WatchProgress.content_id == playback.content_id,
        )
    )
    now = utcnow()
    if progress is None:
        progress = WatchProgress(
            user_id=context.user.id,
            content_type=ContentType.SERIES if playback.episode_id else ContentType.MOVIE,
            content_id=playback.content_id,
            episode_id=playback.episode_id,
            device_id=context.session.device_id,
            position_seconds=position,
            duration_seconds=duration_seconds,
            percentage=percentage,
            completed=completed,
            last_watched_at=now,
        )
        db.add(progress)
    else:
        progress.device_id = context.session.device_id
        progress.position_seconds = position
        progress.duration_seconds = duration_seconds
        progress.percentage = percentage
        progress.completed = completed
        progress.last_watched_at = now
        progress.removed_at = None
    history = await db.scalar(
        select(WatchHistory).where(WatchHistory.playback_session_id == playback.id)
    )
    if history is None:
        history = WatchHistory(
            user_id=context.user.id,
            content_type=ContentType.SERIES if playback.episode_id else ContentType.MOVIE,
            content_id=playback.content_id,
            episode_id=playback.episode_id,
            playback_session_id=playback.id,
            device_id=context.session.device_id,
            position_seconds=position,
            duration_seconds=duration_seconds,
            percentage=percentage,
            completed=completed,
            started_at=playback.created_at,
            last_watched_at=now,
        )
        db.add(history)
    else:
        history.position_seconds = position
        history.duration_seconds = duration_seconds
        history.percentage = percentage
        history.completed = completed
        history.last_watched_at = now
    playback.last_activity_at = now
    if position >= get_settings().MINIMUM_VIEW_SECONDS and playback.view_counted_at is None:
        await db.execute(
            update(Content)
            .where(Content.id == playback.content_id)
            .values(view_count=Content.view_count + 1)
        )
        playback.view_counted_at = now
    await db.flush()
    await db.commit()
    return progress_data(progress)


def progress_data(row: WatchProgress) -> dict[str, Any]:
    return {
        "id": row.id,
        "content_type": row.content_type,
        "content_id": row.content_id,
        "episode_id": row.episode_id,
        "position_seconds": row.position_seconds,
        "duration_seconds": row.duration_seconds,
        "percentage": row.percentage,
        "completed": row.completed,
        "last_watched_at": row.last_watched_at,
    }


async def continue_watching(
    db: AsyncSession, *, user_id: UUID, page: int, limit: int
) -> tuple[list[dict[str, Any]], int]:
    filters = (
        WatchProgress.user_id == user_id,
        WatchProgress.completed.is_(False),
        WatchProgress.removed_at.is_(None),
        WatchProgress.position_seconds > 0,
    )
    total = int(
        await db.scalar(select(func.count()).select_from(WatchProgress).where(*filters)) or 0
    )
    rows = list(
        (
            await db.scalars(
                select(WatchProgress)
                .where(*filters)
                .options(
                    selectinload(WatchProgress.content),
                    selectinload(WatchProgress.episode),
                )
                .order_by(WatchProgress.last_watched_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).all()
    )
    return [
        {
            "progress": progress_data(row),
            "content": content_data(row.content, detailed=False),
            "episode": episode_data(row.episode) if row.episode else None,
        }
        for row in rows
    ], total


async def history_items(
    db: AsyncSession, *, user_id: UUID, page: int, limit: int
) -> tuple[list[dict[str, Any]], int]:
    filters = (WatchHistory.user_id == user_id, WatchHistory.deleted_at.is_(None))
    total = int(
        await db.scalar(select(func.count()).select_from(WatchHistory).where(*filters)) or 0
    )
    rows = list(
        (
            await db.scalars(
                select(WatchHistory)
                .where(*filters)
                .options(
                    selectinload(WatchHistory.content),
                    selectinload(WatchHistory.episode),
                )
                .order_by(WatchHistory.last_watched_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).all()
    )
    return [
        {
            "id": row.id,
            "content": content_data(row.content, detailed=False),
            "episode": episode_data(row.episode) if row.episode else None,
            "position_seconds": row.position_seconds,
            "duration_seconds": row.duration_seconds,
            "percentage": row.percentage,
            "completed": row.completed,
            "started_at": row.started_at,
            "last_watched_at": row.last_watched_at,
            "device_id": row.device_id,
        }
        for row in rows
    ], total


async def remove_continue_item(db: AsyncSession, *, user_id: UUID, progress_id: UUID) -> None:
    row = await db.scalar(
        select(WatchProgress).where(
            WatchProgress.id == progress_id, WatchProgress.user_id == user_id
        )
    )
    if row is None:
        raise AppError("NOT_FOUND", "Continue-watching item not found.", status_code=404)
    row.removed_at = utcnow()
    await db.commit()


async def restart_progress(db: AsyncSession, *, user_id: UUID, progress_id: UUID) -> WatchProgress:
    row = await db.scalar(
        select(WatchProgress).where(
            WatchProgress.id == progress_id, WatchProgress.user_id == user_id
        )
    )
    if row is None:
        raise AppError("NOT_FOUND", "Continue-watching item not found.", status_code=404)
    row.position_seconds = 0
    row.percentage = Decimal("0")
    row.completed = False
    row.removed_at = None
    row.last_watched_at = utcnow()
    await db.commit()
    return row


async def delete_history_item(db: AsyncSession, *, user_id: UUID, history_id: UUID) -> None:
    row = await db.scalar(
        select(WatchHistory).where(
            WatchHistory.id == history_id,
            WatchHistory.user_id == user_id,
            WatchHistory.deleted_at.is_(None),
        )
    )
    if row is None:
        raise AppError("NOT_FOUND", "History item not found.", status_code=404)
    row.deleted_at = utcnow()
    await db.commit()


async def clear_history(db: AsyncSession, *, user_id: UUID) -> int:
    result = await db.execute(
        update(WatchHistory)
        .where(WatchHistory.user_id == user_id, WatchHistory.deleted_at.is_(None))
        .values(deleted_at=utcnow())
    )
    await db.commit()
    return int(cast(CursorResult[Any], result).rowcount or 0)
