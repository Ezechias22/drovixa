from __future__ import annotations

import hashlib
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.integrations.videos.base import VideoMetadata, VideoProvider
from app.models.base import utcnow
from app.models.content import VideoAsset
from app.models.enums import VideoStatus, WebhookProcessingStatus
from app.models.streaming import VideoUploadSession, VideoWebhookEvent
from app.models.user import User
from app.schemas.streaming import UploadSessionCreate


def apply_video_metadata(asset: VideoAsset, metadata: VideoMetadata) -> None:
    asset.provider_asset_id = metadata.provider_asset_id
    forward_rank = {
        VideoStatus.UPLOADING: 0,
        VideoStatus.PROCESSING: 1,
        VideoStatus.READY: 2,
    }
    current_rank = forward_rank.get(asset.status)
    incoming_rank = forward_rank.get(metadata.status)
    if asset.status == VideoStatus.DELETED:
        should_advance = metadata.status == VideoStatus.DELETED
    elif asset.status == VideoStatus.FAILED:
        should_advance = metadata.status in {VideoStatus.FAILED, VideoStatus.DELETED}
    else:
        should_advance = (
            current_rank is None or incoming_rank is None or incoming_rank >= current_rank
        )
    if should_advance:
        asset.status = metadata.status
    if metadata.duration_seconds is not None:
        asset.duration_seconds = metadata.duration_seconds
    if metadata.width is not None:
        asset.width = metadata.width
    if metadata.height is not None:
        asset.height = metadata.height
    if metadata.width and metadata.height:
        asset.aspect_ratio = f"{metadata.width}:{metadata.height}"
    if metadata.thumbnail_url is not None:
        asset.thumbnail_url = metadata.thumbnail_url
    if metadata.playback_id is not None:
        asset.playback_id = metadata.playback_id
    if metadata.error_code is not None or metadata.status == VideoStatus.FAILED:
        asset.provider_error_code = metadata.error_code
    if metadata.error_message is not None or metadata.status == VideoStatus.FAILED:
        asset.provider_error_message = metadata.error_message
    asset.asset_metadata = {
        **(asset.asset_metadata or {}),
        "provider_payload": metadata.raw,
    }
    if asset.status == VideoStatus.READY and asset.ready_at is None:
        asset.ready_at = utcnow()


async def create_upload_session(
    db: AsyncSession,
    *,
    provider: VideoProvider,
    admin: User,
    payload: UploadSessionCreate,
) -> tuple[VideoAsset, VideoUploadSession, str, dict[str, str]]:
    protocol = provider.select_upload_protocol(
        requested=payload.protocol,
        file_size_bytes=payload.file_size_bytes,
    )
    asset_id = uuid4()
    upload = await provider.get_upload_url(
        file_name=payload.file_name,
        content_type=payload.content_type,
        file_size_bytes=payload.file_size_bytes,
        max_duration_seconds=payload.max_duration_seconds,
        protocol=protocol,
        creator_id=str(admin.id),
        external_id=str(asset_id),
    )
    asset = VideoAsset(
        id=asset_id,
        provider=provider.name,
        provider_asset_id=upload.provider_asset_id,
        status=VideoStatus.UPLOADING,
        asset_metadata={
            "source": "direct_upload",
            "file_name": payload.file_name,
            "content_type": payload.content_type,
            "file_size_bytes": payload.file_size_bytes,
            "provider_upload_id": upload.provider_asset_id,
        },
    )
    db.add(asset)
    await db.flush()
    session = VideoUploadSession(
        video_asset_id=asset.id,
        initiated_by_id=admin.id,
        protocol=upload.protocol,
        file_name=payload.file_name,
        content_type=payload.content_type,
        file_size_bytes=payload.file_size_bytes,
        max_duration_seconds=payload.max_duration_seconds,
        expires_at=upload.expires_at,
    )
    db.add(session)
    await db.flush()
    return asset, session, upload.upload_url, upload.headers


async def refresh_video_asset(
    db: AsyncSession, *, provider: VideoProvider, asset: VideoAsset
) -> VideoAsset:
    if asset.provider != provider.name:
        raise AppError(
            "VIDEO_PROVIDER_UNAVAILABLE",
            "The provider for this video asset is unavailable.",
            status_code=503,
        )
    metadata = await provider.get_video_status(asset.provider_asset_id)
    apply_video_metadata(asset, metadata)
    return asset


async def process_video_webhook(
    db: AsyncSession,
    *,
    provider: VideoProvider,
    body: bytes,
    signature: str | None,
    payload: dict[str, Any],
) -> tuple[VideoWebhookEvent, bool]:
    signed_at = provider.verify_webhook(body=body, signature=signature)
    idempotency_key = hashlib.sha256(body).hexdigest()
    existing = await db.scalar(
        select(VideoWebhookEvent).where(
            VideoWebhookEvent.provider == provider.name,
            VideoWebhookEvent.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing, True

    metadata = provider.parse_webhook(payload)
    raw_status = payload.get("status")
    status_data: dict[str, Any] = raw_status if isinstance(raw_status, dict) else {}
    raw_event_type = payload.get("type") or status_data.get("state") or "video.updated"
    event = VideoWebhookEvent(
        provider=provider.name,
        idempotency_key=idempotency_key,
        provider_asset_id=metadata.provider_asset_id,
        event_type=str(raw_event_type),
        signature_timestamp=signed_at,
        payload=payload,
        status=WebhookProcessingStatus.RECEIVED,
    )
    try:
        async with db.begin_nested():
            db.add(event)
            await db.flush()
    except IntegrityError:
        duplicate = await db.scalar(
            select(VideoWebhookEvent).where(
                VideoWebhookEvent.provider == provider.name,
                VideoWebhookEvent.idempotency_key == idempotency_key,
            )
        )
        if duplicate is None:
            raise
        return duplicate, True

    if not metadata.actionable:
        event.status = WebhookProcessingStatus.IGNORED
        event.processed_at = utcnow()
        return event, False

    asset = await db.scalar(
        select(VideoAsset).where(
            VideoAsset.provider == provider.name,
            VideoAsset.provider_asset_id == metadata.provider_asset_id,
        )
    )
    if asset is None and metadata.correlation_id:
        try:
            correlated_id = UUID(metadata.correlation_id)
        except ValueError:
            correlated_id = None
        if correlated_id is not None:
            asset = await db.scalar(
                select(VideoAsset).where(
                    VideoAsset.id == correlated_id,
                    VideoAsset.provider == provider.name,
                )
            )
    if asset is None:
        event.status = WebhookProcessingStatus.IGNORED
        event.processed_at = utcnow()
        return event, False

    apply_video_metadata(asset, metadata)
    upload = await db.scalar(
        select(VideoUploadSession).where(VideoUploadSession.video_asset_id == asset.id)
    )
    if upload and metadata.status in {VideoStatus.PROCESSING, VideoStatus.READY}:
        upload.upload_completed_at = upload.upload_completed_at or utcnow()
    event.status = WebhookProcessingStatus.PROCESSED
    event.processed_at = utcnow()
    return event, False


def upload_session_data(
    asset: VideoAsset,
    session: VideoUploadSession,
    *,
    upload_url: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    return {
        "id": session.id,
        "video_asset_id": asset.id,
        "provider": asset.provider,
        "status": asset.status,
        "protocol": session.protocol,
        "upload_url": upload_url,
        "upload_headers": headers,
        "expires_at": session.expires_at,
        "file": {
            "name": session.file_name,
            "content_type": session.content_type,
            "size_bytes": session.file_size_bytes,
        },
    }


def webhook_data(event: VideoWebhookEvent, *, duplicate: bool) -> dict[str, Any]:
    return {
        "event_id": event.id,
        "status": event.status,
        "duplicate": duplicate,
        "processed_at": event.processed_at,
    }
