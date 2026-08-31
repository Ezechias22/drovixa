from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.administration import NotificationCampaign
from app.models.base import utcnow
from app.models.configuration import FeatureFlag, RemoteConfig
from app.models.content import Content, Series
from app.models.enums import (
    ContentStatus,
    ContentType,
    ContentVisibility,
    Orientation,
    SeriesStatus,
)
from app.models.growth import (
    AdEvent,
    AdPlacement,
    DailyRewardClaim,
    Referral,
    RewardedAdSession,
)
from app.models.monetization import WalletLedger
from app.services.engagement import (
    complete_rewarded_ad_from_ssv,
    queue_publication_notification,
)


async def enable_growth(db: AsyncSession) -> None:
    db.add_all(
        [
            FeatureFlag(
                key=key,
                description=key,
                enabled=True,
                rollout_percentage=100,
                rules={},
            )
            for key in (
                "ads_enabled",
                "daily_rewards_enabled",
                "referrals_enabled",
                "social_login_enabled",
                "watch_party_enabled",
            )
        ]
    )
    await db.commit()


async def published_series(db: AsyncSession) -> Content:
    row = Content(
        type=ContentType.SERIES,
        title="Watch Together Test",
        slug=f"watch-together-{uuid4().hex[:8]}",
        status=ContentStatus.PUBLISHED,
        visibility=ContentVisibility.PUBLIC,
        published_at=utcnow(),
        allowed_countries=[],
        blocked_countries=[],
    )
    db.add(
        Series(
            content=row,
            series_status=SeriesStatus.ONGOING,
            orientation=Orientation.VERTICAL,
        )
    )
    await db.commit()
    return row


async def enable_engagement(db: AsyncSession) -> None:
    db.add_all(
        [
            FeatureFlag(
                key=key,
                description=key,
                enabled=True,
                rollout_percentage=100,
                rules={},
            )
            for key in (
                "rewarded_ads_enabled",
                "premium_offers_enabled",
                "content_notifications_enabled",
                "continue_watching_reminders_enabled",
            )
        ]
    )
    db.add_all(
        [
            RemoteConfig(
                key="admob_rewarded",
                value={"coins_per_ad": 10, "daily_limit": 2},
                description="test",
                is_public=False,
            ),
            RemoteConfig(
                key="premium_engagement",
                value={
                    "max_per_session": 2,
                    "max_per_day": 3,
                    "first_delay_seconds": 90,
                    "repeat_delay_seconds": 480,
                    "notification_cooldown_hours": 72,
                    "continue_after_hours": 24,
                    "continue_cooldown_hours": 48,
                },
                description="test",
                is_public=False,
            ),
        ]
    )
    await db.commit()


async def test_daily_reward_is_idempotent(
    client: AsyncClient, db: AsyncSession, registered: dict[str, object]
) -> None:
    await enable_growth(db)
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    first = await client.post("/api/v1/rewards/daily/claim", headers=headers)
    second = await client.post("/api/v1/rewards/daily/claim", headers=headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["data"]["claimed_today"] is True
    assert first.json()["data"]["claim"]["coins"] == 5
    assert int(await db.scalar(select(func.count()).select_from(DailyRewardClaim)) or 0) == 1
    assert int(await db.scalar(select(func.count()).select_from(WalletLedger)) or 0) == 1


async def test_referral_rewards_both_accounts_once(
    client: AsyncClient, db: AsyncSession, registered: dict[str, object]
) -> None:
    await enable_growth(db)
    inviter_headers = {"Authorization": f"Bearer {registered['access_token']}"}
    summary = await client.get("/api/v1/referrals/me", headers=inviter_headers)
    code = summary.json()["data"]["code"]
    invitee = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "invitee@example.com",
            "name": "Invited Viewer",
            "password": "securepass456",
            "device": {
                "device_id": "invitee-device-1234",
                "name": "Invitee Phone",
                "platform": "android",
            },
        },
    )
    invitee_headers = {"Authorization": f"Bearer {invitee.json()['data']['access_token']}"}
    applied = await client.post(
        "/api/v1/referrals/apply", headers=invitee_headers, json={"code": code}
    )
    repeated = await client.post(
        "/api/v1/referrals/apply", headers=invitee_headers, json={"code": code}
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["data"]["applied"] is True
    assert repeated.status_code == 409
    assert int(await db.scalar(select(func.count()).select_from(Referral)) or 0) == 1
    assert int(await db.scalar(select(func.count()).select_from(WalletLedger)) or 0) == 2


async def test_signed_ad_delivery_only_rewards_once(
    client: AsyncClient, db: AsyncSession, registered: dict[str, object]
) -> None:
    await enable_growth(db)
    db.add(
        AdPlacement(
            key="rewarded-test",
            name="Rewarded test",
            placement="home_feed",
            format="rewarded_video",
            headline="Earn coins",
            countries=[],
            languages=[],
            reward_coins=7,
            daily_cap=3,
            priority=500,
            active=True,
        )
    )
    await db.commit()
    headers = {
        "Authorization": f"Bearer {registered['access_token']}",
        "X-Drovixa-Device-ID": "reward-device-123",
    }
    delivery = await client.get("/api/v1/ads/next?placement=home_feed", headers=headers)
    assert delivery.status_code == 200, delivery.text
    ad = delivery.json()["data"]
    payload = {
        "delivery_id": ad["delivery_id"],
        "session_key": ad["session_key"],
        "event_type": "completed",
    }
    first = await client.post("/api/v1/ads/events", headers=headers, json=payload)
    second = await client.post("/api/v1/ads/events", headers=headers, json=payload)
    assert first.json()["data"]["rewarded"] is True
    assert second.json()["data"]["rewarded"] is False
    assert int(await db.scalar(select(func.count()).select_from(AdEvent)) or 0) == 1
    assert int(await db.scalar(select(func.count()).select_from(WalletLedger)) or 0) == 1


async def test_admob_ssv_credits_exactly_once(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await enable_engagement(db)
    monkeypatch.setattr(
        "app.services.engagement._ad_unit_id", lambda platform: "test-rewarded-unit"
    )
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    created = await client.post(
        "/api/v1/rewards/ads/session",
        headers=headers,
        json={"platform": "android"},
    )
    assert created.status_code == 201, created.text
    session = created.json()["data"]

    async def verified(_: str) -> dict[str, str]:
        return {
            "custom_data": session["custom_data"],
            "transaction_id": "google-transaction-001",
            "user_id": session["user_id"],
            "ad_unit": session["ad_unit_id"],
            "reward_amount": "1",
            "reward_item": "coins",
            "timestamp": "1",
        }

    monkeypatch.setattr("app.services.engagement.verify_admob_signature", verified)
    first = await complete_rewarded_ad_from_ssv(db, raw_query="signed")
    second = await complete_rewarded_ad_from_ssv(db, raw_query="signed")
    assert first == {"recorded": True, "credited": True, "reward_coins": 10}
    assert second["duplicate"] is True
    assert int(await db.scalar(select(func.count()).select_from(RewardedAdSession)) or 0) == 1
    assert int(await db.scalar(select(func.count()).select_from(WalletLedger)) or 0) == 1


async def test_published_content_notification_is_deduplicated(db: AsyncSession) -> None:
    await enable_engagement(db)
    content = await published_series(db)
    first = await queue_publication_notification(db, content_id=content.id)
    second = await queue_publication_notification(db, content_id=content.id)
    await db.commit()
    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert first.action_url == f"/series/{content.slug}"
    assert int(await db.scalar(select(func.count()).select_from(NotificationCampaign)) or 0) == 1


async def test_admin_controls_reward_and_engagement_limits(
    client: AsyncClient,
    db: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await enable_engagement(db)
    response = await client.patch(
        "/api/v1/admin/growth/config",
        headers=admin_headers,
        json={
            "rewarded_ads_enabled": True,
            "premium_offers_enabled": True,
            "content_notifications_enabled": True,
            "continue_watching_reminders_enabled": True,
            "coins_per_ad": 10,
            "daily_limit": 4,
            "max_per_session": 1,
            "max_per_day": 2,
            "first_delay_seconds": 120,
            "repeat_delay_seconds": 600,
            "premium_notification_cooldown_hours": 96,
            "continue_after_hours": 30,
            "continue_cooldown_hours": 72,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["daily_limit"] == 4
    assert response.json()["data"]["max_per_session"] == 1


async def test_watch_party_host_membership_and_admin_summary(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    admin_headers: dict[str, str],
) -> None:
    await enable_growth(db)
    content = await published_series(db)
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    created = await client.post(
        "/api/v1/watch-parties",
        headers=headers,
        json={"content_id": str(content.id), "title": "Friday Watch", "max_members": 5},
    )
    assert created.status_code == 201, created.text
    party = created.json()["data"]
    assert party["is_host"] is True
    assert len(party["members"]) == 1
    state = await client.patch(
        f"/api/v1/watch-parties/{party['invite_code']}/state",
        headers=headers,
        json={"position_seconds": 12, "paused": False, "status": "playing"},
    )
    assert state.json()["data"]["position_seconds"] == 12
    message = await client.post(
        f"/api/v1/watch-parties/{party['invite_code']}/messages",
        headers=headers,
        json={"message": "Ann gade ansanm!"},
    )
    assert message.status_code == 201
    admin = await client.get("/api/v1/admin/growth/summary", headers=admin_headers)
    assert admin.status_code == 200, admin.text
    assert admin.json()["data"]["active_watch_parties"] == 1


async def test_social_login_config_stays_closed_without_provider_ids(
    client: AsyncClient, db: AsyncSession
) -> None:
    await enable_growth(db)
    config = await client.get("/api/v1/growth/config")
    assert config.status_code == 200
    assert config.json()["data"]["google_login"] is False
    response = await client.post(
        "/api/v1/auth/social",
        json={
            "provider": "google",
            "id_token": "x" * 80,
            "device": {
                "device_id": "social-test-device",
                "name": "Social Test",
                "platform": "web",
            },
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SOCIAL_LOGIN_NOT_CONFIGURED"
