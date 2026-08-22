from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.api.deps import DbSession
from app.core.exceptions import AppError
from app.integrations.videos import VideoProvider, get_video_provider
from app.schemas.common import success
from app.services.videos import process_video_webhook, webhook_data

router = APIRouter(prefix="/webhooks/videos", tags=["Video webhooks"])
Provider = Annotated[VideoProvider, Depends(get_video_provider)]


@router.post("/{provider_name}")
async def video_webhook(
    provider_name: str,
    request: Request,
    db: DbSession,
    provider: Provider,
) -> dict[str, Any]:
    if provider_name != provider.name:
        raise AppError("NOT_FOUND", "Video provider not found.", status_code=404)
    body = await request.body()
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AppError(
            "INVALID_WEBHOOK_PAYLOAD", "Webhook payload is invalid.", status_code=400
        ) from exc
    if not isinstance(payload, dict):
        raise AppError("INVALID_WEBHOOK_PAYLOAD", "Webhook payload is invalid.", status_code=400)
    event, duplicate = await process_video_webhook(
        db,
        provider=provider,
        body=body,
        signature=request.headers.get(provider.webhook_signature_header),
        payload=payload,
    )
    await db.commit()
    return success(webhook_data(event, duplicate=duplicate))
