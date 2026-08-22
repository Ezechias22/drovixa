from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select

from app.api.deps import DbSession, require_permission
from app.core.exceptions import AppError
from app.integrations.videos import VideoProvider, get_video_provider
from app.models.content import Episode, Movie, VideoAsset
from app.models.user import User
from app.schemas.common import success
from app.schemas.streaming import SourceVideoIngestCreate, UploadSessionCreate
from app.services.audit import add_audit_log
from app.services.content import snapshot, video_asset_data
from app.services.videos import (
    apply_video_metadata,
    create_upload_session,
    refresh_video_asset,
    upload_session_data,
)

router = APIRouter(prefix="/admin", tags=["Admin streaming"])
Creator = Annotated[User, require_permission("content.create")]
Editor = Annotated[User, require_permission("content.edit")]
Deleter = Annotated[User, require_permission("content.delete")]
Provider = Annotated[VideoProvider, Depends(get_video_provider)]


def _audit(
    db: DbSession,
    *,
    request: Request,
    admin: User,
    action: str,
    entity_id: UUID,
    old: dict[str, Any] | None,
    new: dict[str, Any] | None,
) -> None:
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action=action,
        entity_type="video_asset",
        entity_id=str(entity_id),
        old_value=jsonable_encoder(old) if old is not None else None,
        new_value=jsonable_encoder(new) if new is not None else None,
    )


async def _asset(db: DbSession, asset_id: UUID) -> VideoAsset:
    row = await db.scalar(
        select(VideoAsset).where(VideoAsset.id == asset_id, VideoAsset.deleted_at.is_(None))
    )
    if row is None:
        raise AppError("NOT_FOUND", "Video asset not found.", status_code=404)
    return row


@router.post("/video-assets/upload-sessions", status_code=status.HTTP_201_CREATED)
async def admin_create_upload_session(
    payload: UploadSessionCreate,
    request: Request,
    admin: Creator,
    db: DbSession,
    provider: Provider,
) -> dict[str, Any]:
    asset, upload, upload_url, headers = await create_upload_session(
        db, provider=provider, admin=admin, payload=payload
    )
    result = upload_session_data(asset, upload, upload_url=upload_url, headers=headers)
    _audit(
        db,
        request=request,
        admin=admin,
        action="video_asset.upload_session.create",
        entity_id=asset.id,
        old=None,
        new={key: value for key, value in result.items() if key != "upload_url"},
    )
    await db.commit()
    return success(result)


@router.post("/video-assets/ingest", status_code=status.HTTP_201_CREATED)
async def admin_ingest_source_video(
    payload: SourceVideoIngestCreate,
    request: Request,
    admin: Creator,
    db: DbSession,
    provider: Provider,
) -> dict[str, Any]:
    metadata = await provider.upload_video(source_url=payload.source_url, name=payload.file_name)
    asset = VideoAsset(
        provider=provider.name,
        provider_asset_id=metadata.provider_asset_id,
        asset_metadata={"source": "url_ingest", "file_name": payload.file_name},
    )
    apply_video_metadata(asset, metadata)
    db.add(asset)
    await db.flush()
    result = video_asset_data(asset)
    _audit(
        db,
        request=request,
        admin=admin,
        action="video_asset.ingest.create",
        entity_id=asset.id,
        old=None,
        new=result,
    )
    await db.commit()
    return success(result)


@router.post("/video-assets/{asset_id}/refresh")
async def admin_refresh_video_status(
    asset_id: UUID,
    request: Request,
    admin: Editor,
    db: DbSession,
    provider: Provider,
) -> dict[str, Any]:
    asset = await _asset(db, asset_id)
    old = snapshot(asset)
    await refresh_video_asset(db, provider=provider, asset=asset)
    new = video_asset_data(asset)
    _audit(
        db,
        request=request,
        admin=admin,
        action="video_asset.status.refresh",
        entity_id=asset.id,
        old=old,
        new=new,
    )
    await db.commit()
    return success(new)


@router.delete("/video-assets/{asset_id}/provider")
async def admin_delete_provider_video(
    asset_id: UUID,
    request: Request,
    admin: Deleter,
    db: DbSession,
    provider: Provider,
) -> dict[str, Any]:
    asset = await _asset(db, asset_id)
    in_use = await db.scalar(
        select(Episode.id)
        .where(Episode.video_asset_id == asset.id, Episode.deleted_at.is_(None))
        .union(select(Movie.id).where(Movie.video_asset_id == asset.id))
        .limit(1)
    )
    if in_use is not None:
        raise AppError(
            "VIDEO_ASSET_IN_USE",
            "Detach the video asset from content before deleting it.",
            status_code=409,
        )
    if asset.provider != provider.name:
        raise AppError("VIDEO_PROVIDER_UNAVAILABLE", "Video provider unavailable.", status_code=503)
    old = snapshot(asset)
    await provider.delete_video(asset.provider_asset_id)
    from app.models.base import utcnow
    from app.models.enums import VideoStatus

    asset.status = VideoStatus.DELETED
    asset.deleted_at = utcnow()
    _audit(
        db,
        request=request,
        admin=admin,
        action="video_asset.provider.delete",
        entity_id=asset.id,
        old=old,
        new={"status": "deleted"},
    )
    await db.commit()
    return success({"id": asset.id, "deleted": True})
