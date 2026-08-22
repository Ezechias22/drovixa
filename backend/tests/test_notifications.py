from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.notifications.base import PushMessage, PushResult
from app.models.administration import NotificationCampaign
from app.models.base import utcnow
from app.models.notifications import NotificationDelivery, PushToken
from app.services.notifications import (
    deliver_campaign_push,
    dispatch_due_notification_campaigns,
)


class SuccessfulPushProvider:
    name = "firebase"
    enabled = True

    async def send(self, *, tokens: list[str], message: PushMessage) -> list[PushResult]:
        assert message.title
        return [
            PushResult(success=True, message_id=f"firebase-message-{index}")
            for index, _ in enumerate(tokens)
        ]


async def test_push_token_lifecycle_redacts_the_raw_token(
    client: AsyncClient, registered: dict[str, object]
) -> None:
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    raw_token = "fcm-test-token-that-is-long-enough-123456789"

    config = await client.get("/api/v1/push/config")
    assert config.status_code == 200
    assert config.json()["data"] == {
        "enabled": False,
        "provider": "disabled",
        "project_id": None,
    }

    created = await client.post(
        "/api/v1/push-tokens",
        headers=headers,
        json={
            "provider": "fcm",
            "platform": "android",
            "token": raw_token,
            "app_version": "0.9.0",
            "locale": "HT-ht",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["data"]["token_hint"] == f"...{raw_token[-6:]}"
    assert raw_token not in created.text

    listed = await client.get("/api/v1/push-tokens", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["data"][0]["locale"] == "ht-ht"
    assert raw_token not in listed.text

    removed = await client.delete("/api/v1/push-tokens/current", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["data"]["deactivated"] == 1


async def test_admin_campaign_creates_and_delivers_firebase_rows(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    token = await client.post(
        "/api/v1/push-tokens",
        headers=headers,
        json={
            "provider": "fcm",
            "platform": "android",
            "token": "fcm-campaign-token-that-is-long-enough-987654321",
        },
    )
    assert token.status_code == 201, token.text

    campaign = await client.post(
        "/api/v1/admin/notification-campaigns",
        headers=admin_headers,
        json={
            "name": "Phase 9 push test",
            "type": "system",
            "title": "Drovixa notification",
            "body": "Firebase delivery is ready.",
            "audience": {"segment": "all"},
            "channels": ["in_app", "push"],
        },
    )
    assert campaign.status_code == 201, campaign.text
    campaign_id = UUID(campaign.json()["data"]["id"])

    from app.workers.celery_app import deliver_campaign_push_task

    monkeypatch.setattr(deliver_campaign_push_task, "delay", lambda *_: None)
    queued = await client.post(
        f"/api/v1/admin/notification-campaigns/{campaign_id}/send",
        headers=admin_headers,
        json={"send_now": True},
    )
    assert queued.status_code == 200, queued.text
    assert queued.json()["data"]["status"] == "queued"

    monkeypatch.setattr(
        "app.services.notifications.get_push_provider",
        lambda *_: SuccessfulPushProvider(),
    )
    summary = await deliver_campaign_push(db, campaign_id=campaign_id)
    assert summary == {"sent": 1, "failed": 0, "pending": 0}
    assert int(
        await db.scalar(
            select(func.count(NotificationDelivery.id)).where(
                NotificationDelivery.campaign_id == campaign_id,
                NotificationDelivery.status == "sent",
            )
        )
        or 0
    ) == 1
    registered_token = await db.scalar(select(PushToken))
    assert registered_token is not None
    assert registered_token.last_success_at is not None

    deliveries = await client.get(
        f"/api/v1/admin/notification-campaigns/{campaign_id}/deliveries",
        headers=admin_headers,
    )
    assert deliveries.status_code == 200
    assert deliveries.json()["data"]["status"] == "sent"
    assert deliveries.json()["data"]["deliveries"][0]["count"] == 1


async def test_admin_campaign_can_deliver_inline_without_celery_worker(
    client: AsyncClient,
    registered: dict[str, object],
    admin_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    token = await client.post(
        "/api/v1/push-tokens",
        headers=headers,
        json={
            "provider": "fcm",
            "platform": "android",
            "token": "fcm-inline-token-that-is-long-enough-123456789",
        },
    )
    assert token.status_code == 201, token.text

    campaign = await client.post(
        "/api/v1/admin/notification-campaigns",
        headers=admin_headers,
        json={
            "name": "Render free inline test",
            "type": "system",
            "title": "Drovixa free staging",
            "body": "Inline Firebase delivery works without Celery.",
            "audience": {"segment": "all"},
            "channels": ["in_app", "push"],
        },
    )
    assert campaign.status_code == 201, campaign.text
    campaign_id = campaign.json()["data"]["id"]

    monkeypatch.setattr(
        "app.routes.admin_operations.get_settings",
        lambda: SimpleNamespace(NOTIFICATION_DELIVERY_MODE="inline"),
    )
    monkeypatch.setattr(
        "app.services.notifications.get_push_provider",
        lambda *_: SuccessfulPushProvider(),
    )
    sent = await client.post(
        f"/api/v1/admin/notification-campaigns/{campaign_id}/send",
        headers=admin_headers,
        json={"send_now": True},
    )

    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["status"] == "sent"


async def test_free_staging_poll_dispatches_due_scheduled_campaign(
    client: AsyncClient,
    db: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    campaign = await client.post(
        "/api/v1/admin/notification-campaigns",
        headers=admin_headers,
        json={
            "name": "Render free scheduled test",
            "type": "system",
            "title": "Scheduled Drovixa notice",
            "body": "The API polling fallback dispatches this campaign.",
            "scheduled_at": (utcnow() + timedelta(hours=1)).isoformat(),
            "audience": {"segment": "all"},
            "channels": ["in_app"],
        },
    )
    assert campaign.status_code == 201, campaign.text
    campaign_id = UUID(campaign.json()["data"]["id"])
    row = await db.get(NotificationCampaign, campaign_id)
    assert row is not None
    row.scheduled_at = utcnow() - timedelta(seconds=1)
    await db.commit()

    dispatched = await dispatch_due_notification_campaigns(db)
    await db.refresh(row)

    assert dispatched == 1
    assert row.status == "sent"
