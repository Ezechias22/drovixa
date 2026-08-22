from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.integrations.notifications import get_push_provider
from app.integrations.notifications.base import PushMessage
from app.models.administration import NotificationCampaign
from app.models.base import utcnow
from app.models.notifications import NotificationDelivery, PushToken
from app.schemas.notifications import PushTokenRegistration


def push_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def push_token_data(row: PushToken) -> dict[str, Any]:
    return {
        "id": row.id,
        "provider": row.provider,
        "platform": row.platform,
        "device_id": row.device_id,
        "token_hint": f"...{row.token[-6:]}",
        "active": row.active,
        "app_version": row.app_version,
        "locale": row.locale,
        "last_registered_at": row.last_registered_at,
        "last_success_at": row.last_success_at,
        "failure_count": row.failure_count,
        "disabled_at": row.disabled_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def push_provider_status() -> dict[str, Any]:
    settings = get_settings()
    configured = bool(
        settings.PUSH_PROVIDER == "firebase"
        and settings.FIREBASE_PROJECT_ID
        and settings.FIREBASE_SERVICE_ACCOUNT_JSON_B64
    )
    return {
        "provider": settings.PUSH_PROVIDER,
        "configured": configured,
        "project_id": settings.FIREBASE_PROJECT_ID if configured else None,
        "dry_run": settings.FIREBASE_DRY_RUN,
        "batch_size": settings.PUSH_BATCH_SIZE,
    }


async def register_push_token(
    db: AsyncSession,
    *,
    user_id: UUID,
    device_id: str,
    payload: PushTokenRegistration,
) -> PushToken:
    digest = push_token_hash(payload.token)
    token_row = await db.scalar(select(PushToken).where(PushToken.token_hash == digest))
    device_row = await db.scalar(
        select(PushToken).where(
            PushToken.user_id == user_id,
            PushToken.device_id == device_id,
            PushToken.provider == payload.provider,
        )
    )
    if token_row is not None and device_row is not None and token_row.id != device_row.id:
        await db.execute(delete(PushToken).where(PushToken.id == device_row.id))
        await db.flush()
    row = token_row or device_row
    if row is None:
        row = PushToken(
            user_id=user_id,
            device_id=device_id,
            provider=payload.provider,
            platform=payload.platform,
            token=payload.token,
            token_hash=digest,
        )
        db.add(row)
    row.user_id = user_id
    row.device_id = device_id
    row.provider = payload.provider
    row.platform = payload.platform
    row.token = payload.token
    row.token_hash = digest
    row.active = True
    row.app_version = payload.app_version
    row.locale = payload.locale
    row.last_registered_at = utcnow()
    row.failure_count = 0
    row.disabled_at = None
    await db.commit()
    return row


async def deactivate_push_token(
    db: AsyncSession, *, user_id: UUID, push_token_id: UUID
) -> PushToken:
    row = await db.scalar(
        select(PushToken).where(PushToken.id == push_token_id, PushToken.user_id == user_id)
    )
    if row is None:
        raise AppError("NOT_FOUND", "Push token not found.", status_code=404)
    row.active = False
    row.disabled_at = utcnow()
    await db.commit()
    return row


async def deactivate_device_push_tokens(
    db: AsyncSession, *, user_id: UUID, device_id: str, commit: bool = True
) -> int:
    result = await db.execute(
        update(PushToken)
        .where(
            PushToken.user_id == user_id,
            PushToken.device_id == device_id,
            PushToken.active.is_(True),
        )
        .values(active=False, disabled_at=utcnow())
    )
    if commit:
        await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


async def create_campaign_deliveries(
    db: AsyncSession, *, campaign: NotificationCampaign, user_ids: list[UUID]
) -> int:
    if "push" not in campaign.channels or not user_ids:
        return 0
    tokens = list(
        await db.scalars(
            select(PushToken).where(
                PushToken.user_id.in_(user_ids),
                PushToken.active.is_(True),
                PushToken.provider == "fcm",
            )
        )
    )
    db.add_all(
        [
            NotificationDelivery(
                campaign_id=campaign.id,
                user_id=token.user_id,
                push_token_id=token.id,
                channel="push",
                provider="firebase",
                status="pending",
            )
            for token in tokens
        ]
    )
    await db.flush()
    return len(tokens)


def _invalid_token_error(code: str | None) -> bool:
    normalized = (code or "").casefold().replace("_", "").replace("-", "")
    return "unregistered" in normalized or "invalidargument" in normalized


def _campaign_metadata(campaign: NotificationCampaign) -> dict[str, Any]:
    return campaign.campaign_metadata if isinstance(campaign.campaign_metadata, dict) else {}


async def deliver_campaign_push(db: AsyncSession, *, campaign_id: UUID) -> dict[str, int]:
    campaign = await db.get(NotificationCampaign, campaign_id)
    if campaign is None:
        raise AppError("NOT_FOUND", "Notification campaign not found.", status_code=404)
    rows = list(
        (
            await db.execute(
                select(NotificationDelivery, PushToken)
                .join(PushToken, PushToken.id == NotificationDelivery.push_token_id)
                .where(
                    NotificationDelivery.campaign_id == campaign_id,
                    NotificationDelivery.channel == "push",
                    NotificationDelivery.status.in_(["pending", "retry"]),
                    PushToken.active.is_(True),
                )
                .order_by(NotificationDelivery.created_at)
            )
        ).all()
    )
    settings = get_settings()
    provider = get_push_provider(settings)
    message = PushMessage(
        title=campaign.title,
        body=campaign.body,
        image_url=campaign.image_url,
        action_url=campaign.action_url,
        data={
            "campaign_id": str(campaign.id),
            "type": campaign.type,
            "action_url": campaign.action_url or "drovixa://notifications",
        },
    )
    for offset in range(0, len(rows), settings.PUSH_BATCH_SIZE):
        batch = rows[offset : offset + settings.PUSH_BATCH_SIZE]
        results = await provider.send(tokens=[token.token for _, token in batch], message=message)
        now = utcnow()
        for (delivery, token), result in zip(batch, results, strict=True):
            delivery.attempted_at = now
            if result.success:
                delivery.status = "sent"
                delivery.provider_message_id = result.message_id
                delivery.delivered_at = now
                delivery.error_code = None
                delivery.error_message = None
                token.last_success_at = now
                token.failure_count = 0
            else:
                delivery.status = "failed"
                delivery.error_code = result.error_code
                delivery.error_message = result.error_message
                token.failure_count += 1
                if _invalid_token_error(result.error_code):
                    token.active = False
                    token.disabled_at = now
        await db.commit()

    counts = Counter(
        status
        for status in await db.scalars(
            select(NotificationDelivery.status).where(
                NotificationDelivery.campaign_id == campaign_id,
                NotificationDelivery.channel == "push",
            )
        )
    )
    successful = counts["sent"]
    failed = counts["failed"]
    pending = counts["pending"] + counts["retry"]
    campaign.failure_count = failed
    if pending:
        campaign.status = "processing"
    elif failed and not successful and "in_app" not in campaign.channels:
        campaign.status = "failed"
    elif failed:
        campaign.status = "partial"
    else:
        campaign.status = "sent"
    if not pending:
        campaign.sent_at = campaign.sent_at or utcnow()
    metadata = _campaign_metadata(campaign)
    existing_delivery = metadata.get("delivery")
    if not isinstance(existing_delivery, dict):
        existing_delivery = {}
    campaign.campaign_metadata = {
        **metadata,
        "delivery": {
            **existing_delivery,
            "push": {
                "provider": provider.name,
                "registered_tokens": len(rows),
                "sent": successful,
                "failed": failed,
                "pending": pending,
            },
        },
    }
    await db.commit()
    return {"sent": successful, "failed": failed, "pending": pending}


async def campaign_delivery_summary(db: AsyncSession, *, campaign_id: UUID) -> dict[str, Any]:
    campaign = await db.get(NotificationCampaign, campaign_id)
    if campaign is None:
        raise AppError("NOT_FOUND", "Notification campaign not found.", status_code=404)
    rows = (
        await db.execute(
            select(
                NotificationDelivery.channel,
                NotificationDelivery.provider,
                NotificationDelivery.status,
                func.count(NotificationDelivery.id),
            )
            .where(NotificationDelivery.campaign_id == campaign_id)
            .group_by(
                NotificationDelivery.channel,
                NotificationDelivery.provider,
                NotificationDelivery.status,
            )
        )
    ).all()
    return {
        "campaign_id": campaign_id,
        "status": campaign.status,
        "deliveries": [
            {"channel": channel, "provider": provider, "status": status, "count": count}
            for channel, provider, status, count in rows
        ],
    }


async def disable_user_push_tokens(
    db: AsyncSession, *, user_id: UUID, commit: bool = True
) -> int:
    result = await db.execute(
        update(PushToken)
        .where(PushToken.user_id == user_id, PushToken.active.is_(True))
        .values(active=False, disabled_at=utcnow())
    )
    if commit:
        await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)
