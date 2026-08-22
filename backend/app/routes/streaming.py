from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request

from app.api.deps import CurrentContext, DbSession, OptionalContext
from app.core.rate_limit import rate_limit
from app.integrations.videos import VideoProvider, get_video_provider
from app.models.enums import ContentType
from app.schemas.common import success
from app.schemas.streaming import HistoryClearInput, PlaybackAuthorizeInput, ProgressSyncInput
from app.services.streaming import (
    authorize_playback,
    clear_history,
    continue_watching,
    delete_history_item,
    history_items,
    remove_continue_item,
    restart_progress,
    sync_progress,
)

router = APIRouter(tags=["Streaming"])
Provider = Annotated[VideoProvider, Depends(get_video_provider)]
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]
ProfileHeader = Annotated[UUID | None, Header(alias="X-Drovixa-Profile-ID")]


def _meta(page: int, limit: int, total: int) -> dict[str, int]:
    return {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit}


@router.post(
    "/playback/{episode_id}/authorize",
    dependencies=[Depends(rate_limit("playback_authorize", requests=60, window_seconds=60))],
)
async def authorize_episode_compat(
    episode_id: UUID,
    payload: PlaybackAuthorizeInput,
    request: Request,
    context: OptionalContext,
    db: DbSession,
    provider: Provider,
    profile_id: ProfileHeader = None,
) -> dict[str, Any]:
    return success(
        await authorize_playback(
            db,
            provider=provider,
            request=request,
            context=context,
            target_type=ContentType.SERIES,
            target_id=episode_id,
            client_device_id=payload.client_device_id,
            profile_id=profile_id,
        )
    )


@router.post(
    "/playback/episodes/{episode_id}/authorize",
    dependencies=[Depends(rate_limit("playback_authorize", requests=60, window_seconds=60))],
)
async def authorize_episode(
    episode_id: UUID,
    payload: PlaybackAuthorizeInput,
    request: Request,
    context: OptionalContext,
    db: DbSession,
    provider: Provider,
    profile_id: ProfileHeader = None,
) -> dict[str, Any]:
    return success(
        await authorize_playback(
            db,
            provider=provider,
            request=request,
            context=context,
            target_type=ContentType.SERIES,
            target_id=episode_id,
            client_device_id=payload.client_device_id,
            profile_id=profile_id,
        )
    )


@router.post(
    "/playback/movies/{movie_id}/authorize",
    dependencies=[Depends(rate_limit("playback_authorize", requests=60, window_seconds=60))],
)
async def authorize_movie(
    movie_id: UUID,
    payload: PlaybackAuthorizeInput,
    request: Request,
    context: OptionalContext,
    db: DbSession,
    provider: Provider,
    profile_id: ProfileHeader = None,
) -> dict[str, Any]:
    return success(
        await authorize_playback(
            db,
            provider=provider,
            request=request,
            context=context,
            target_type=ContentType.MOVIE,
            target_id=movie_id,
            client_device_id=payload.client_device_id,
            profile_id=profile_id,
        )
    )


@router.post(
    "/progress",
    dependencies=[Depends(rate_limit("progress_sync", requests=240, window_seconds=60))],
)
async def save_progress(
    payload: ProgressSyncInput,
    context: CurrentContext,
    db: DbSession,
) -> dict[str, Any]:
    return success(
        await sync_progress(
            db,
            context=context,
            playback_session_id=payload.playback_session_id,
            position_seconds=payload.position_seconds,
            duration_seconds=payload.duration_seconds,
        )
    )


@router.get("/continue-watching")
async def get_continue_watching(
    context: CurrentContext,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 20,
) -> dict[str, Any]:
    rows, total = await continue_watching(db, user_id=context.user.id, page=page, limit=limit)
    return success(rows, meta=_meta(page, limit, total))


@router.delete("/continue-watching/{progress_id}")
async def delete_continue_watching(
    progress_id: UUID, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    await remove_continue_item(db, user_id=context.user.id, progress_id=progress_id)
    return success({"id": progress_id, "removed": True})


@router.post("/continue-watching/{progress_id}/restart")
async def restart_continue_watching(
    progress_id: UUID, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    row = await restart_progress(db, user_id=context.user.id, progress_id=progress_id)
    return success({"id": row.id, "position_seconds": 0, "completed": False})


@router.get("/history")
async def get_history(
    context: CurrentContext,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 20,
) -> dict[str, Any]:
    rows, total = await history_items(db, user_id=context.user.id, page=page, limit=limit)
    return success(rows, meta=_meta(page, limit, total))


@router.delete("/history/{history_id}")
async def delete_history(
    history_id: UUID, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    await delete_history_item(db, user_id=context.user.id, history_id=history_id)
    return success({"id": history_id, "deleted": True})


@router.delete("/history")
async def delete_all_history(
    payload: HistoryClearInput, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    del payload
    count = await clear_history(db, user_id=context.user.id)
    return success({"deleted": count})
