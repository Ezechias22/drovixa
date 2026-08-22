from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.deps import CurrentContext, DbSession, require_feature_enabled
from app.integrations.videos import VideoProvider, get_video_provider
from app.models.enums import ContentType
from app.schemas.common import success
from app.schemas.personalization import (
    CastHeartbeatInput,
    CastSessionInput,
    DownloadAuthorizeInput,
    DownloadStatusInput,
    ProfileCreate,
    ProfilePinVerify,
    ProfileUpdate,
    RatingInput,
)
from app.services.personalization import (
    authorize_download,
    cast_data,
    create_profile,
    delete_profile,
    delete_rating,
    get_rating,
    list_downloads,
    list_profiles,
    profile_data,
    rate_content,
    start_cast_session,
    update_cast_session,
    update_download_status,
    update_profile,
    verify_download,
    verify_profile_pin,
)

router = APIRouter(tags=["Profiles and devices"])
Provider = Annotated[VideoProvider, Depends(get_video_provider)]
ProfileHeader = Annotated[UUID | None, Header(alias="X-Drovixa-Profile-ID")]


@router.get("/profiles")
async def profiles(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    return success(await list_profiles(db, context))


@router.post(
    "/profiles",
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        require_feature_enabled("multi_profile_enabled", error_code="MULTI_PROFILE_DISABLED")
    ],
)
async def add_profile(
    payload: ProfileCreate, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    return success(profile_data(await create_profile(db, context=context, payload=payload)))


@router.patch("/profiles/{profile_id}")
async def patch_profile(
    profile_id: UUID, payload: ProfileUpdate, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    return success(
        profile_data(
            await update_profile(db, context=context, profile_id=profile_id, payload=payload)
        )
    )


@router.delete("/profiles/{profile_id}")
async def remove_profile(
    profile_id: UUID, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    await delete_profile(db, context=context, profile_id=profile_id)
    return success({"id": profile_id, "deleted": True})


@router.post("/profiles/{profile_id}/verify-pin")
async def check_profile_pin(
    profile_id: UUID,
    payload: ProfilePinVerify,
    context: CurrentContext,
    db: DbSession,
) -> dict[str, Any]:
    return success(
        {
            "id": profile_id,
            "valid": await verify_profile_pin(
                db, context=context, profile_id=profile_id, pin=payload.pin
            ),
        }
    )


@router.get(
    "/ratings/{content_id}",
    dependencies=[require_feature_enabled("ratings_enabled", error_code="RATINGS_DISABLED")],
)
async def rating(
    content_id: UUID,
    context: CurrentContext,
    db: DbSession,
    profile_id: ProfileHeader = None,
) -> dict[str, Any]:
    return success(
        await get_rating(db, context=context, profile_id=profile_id, content_id=content_id)
    )


@router.put(
    "/ratings/{content_id}",
    dependencies=[require_feature_enabled("ratings_enabled", error_code="RATINGS_DISABLED")],
)
async def save_rating(
    content_id: UUID,
    payload: RatingInput,
    context: CurrentContext,
    db: DbSession,
    profile_id: ProfileHeader = None,
) -> dict[str, Any]:
    return success(
        await rate_content(
            db,
            context=context,
            profile_id=profile_id,
            content_id=content_id,
            score=payload.score,
        )
    )


@router.delete(
    "/ratings/{content_id}",
    dependencies=[require_feature_enabled("ratings_enabled", error_code="RATINGS_DISABLED")],
)
async def remove_rating(
    content_id: UUID,
    context: CurrentContext,
    db: DbSession,
    profile_id: ProfileHeader = None,
) -> dict[str, Any]:
    return success(
        await delete_rating(db, context=context, profile_id=profile_id, content_id=content_id)
    )


@router.post(
    "/downloads/episodes/{episode_id}/authorize",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_feature_enabled("downloads_enabled", error_code="DOWNLOADS_DISABLED")],
)
async def authorize_episode_download(
    episode_id: UUID,
    payload: DownloadAuthorizeInput,
    request: Request,
    context: CurrentContext,
    db: DbSession,
    provider: Provider,
) -> dict[str, Any]:
    return success(
        await authorize_download(
            db,
            provider=provider,
            request=request,
            context=context,
            target_type=ContentType.SERIES,
            target_id=episode_id,
            profile_id=payload.profile_id,
            quality=payload.quality,
        )
    )


@router.post(
    "/downloads/movies/{movie_id}/authorize",
    status_code=status.HTTP_201_CREATED,
    dependencies=[require_feature_enabled("downloads_enabled", error_code="DOWNLOADS_DISABLED")],
)
async def authorize_movie_download(
    movie_id: UUID,
    payload: DownloadAuthorizeInput,
    request: Request,
    context: CurrentContext,
    db: DbSession,
    provider: Provider,
) -> dict[str, Any]:
    return success(
        await authorize_download(
            db,
            provider=provider,
            request=request,
            context=context,
            target_type=ContentType.MOVIE,
            target_id=movie_id,
            profile_id=payload.profile_id,
            quality=payload.quality,
        )
    )


@router.get("/downloads")
async def downloads(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    return success(await list_downloads(db, context=context))


@router.patch("/downloads/{license_id}")
async def patch_download(
    license_id: UUID,
    payload: DownloadStatusInput,
    context: CurrentContext,
    db: DbSession,
) -> dict[str, Any]:
    return success(
        await update_download_status(
            db,
            context=context,
            license_id=license_id,
            status=payload.status,
            bytes_downloaded=payload.bytes_downloaded,
        )
    )


@router.post("/downloads/{license_id}/verify")
async def verify_download_license(
    license_id: UUID,
    context: CurrentContext,
    db: DbSession,
    license_token: Annotated[str, Header(alias="X-Drovixa-Download-License")],
) -> dict[str, Any]:
    return success(
        await verify_download(
            db,
            context=context,
            license_id=license_id,
            raw_token=license_token,
        )
    )


@router.post("/cast-sessions", status_code=status.HTTP_201_CREATED)
async def create_cast(
    payload: CastSessionInput, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    return success(
        cast_data(
            await start_cast_session(
                db,
                context=context,
                profile_id=payload.profile_id,
                playback_session_id=payload.playback_session_id,
                target_device_id=payload.target_device_id,
                target_device_name=payload.target_device_name,
                target_type=payload.target_type,
            )
        )
    )


@router.patch("/cast-sessions/{cast_id}")
async def heartbeat_cast(
    cast_id: UUID,
    payload: CastHeartbeatInput,
    context: CurrentContext,
    db: DbSession,
) -> dict[str, Any]:
    return success(
        cast_data(
            await update_cast_session(db, context=context, cast_id=cast_id, status=payload.status)
        )
    )
