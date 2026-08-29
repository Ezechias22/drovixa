from __future__ import annotations

from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.base import utcnow
from app.models.content import Content, Series
from app.models.enums import (
    ContentStatus,
    ContentType,
    ContentVisibility,
    Orientation,
    SeriesStatus,
)
from app.models.experience import Notification
from app.models.monetization import Subscription


def test_subscription_period_columns_are_timezone_aware() -> None:
    for column_name in ("starts_at", "current_period_start", "current_period_end"):
        assert Subscription.__table__.c[column_name].type.timezone is True


async def published_content(db: AsyncSession) -> Content:
    content = Content(
        type=ContentType.SERIES,
        title="Admin Spotlight",
        slug=f"admin-spotlight-{uuid4().hex[:8]}",
        status=ContentStatus.PUBLISHED,
        visibility=ContentVisibility.PUBLIC,
        published_at=utcnow(),
        featured=True,
        allowed_countries=[],
        blocked_countries=[],
    )
    db.add(
        Series(
            content=content,
            series_status=SeriesStatus.ONGOING,
            orientation=Orientation.VERTICAL,
        )
    )
    await db.commit()
    return content


async def test_regular_user_cannot_view_admin_dashboard(
    client: AsyncClient, registered: dict[str, object]
) -> None:
    response = await client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {registered['access_token']}"},
    )
    assert response.status_code == 403


async def test_admin_dashboard_users_roles_and_status_controls(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:

    second = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "second-viewer@example.com",
            "name": "Second Viewer",
            "password": "securepass123",
            "device": {
                "device_id": "second-device-12345678",
                "name": "Second Phone",
                "platform": "android",
            },
        },
    )
    assert second.status_code == 201
    second_id = second.json()["data"]["user"]["id"]

    dashboard = await client.get("/api/v1/admin/dashboard", headers=admin_headers)
    users = await client.get("/api/v1/admin/users", headers=admin_headers)
    roles = await client.get("/api/v1/admin/roles", headers=admin_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["data"]["cards"]["users_total"] == 2
    assert users.json()["meta"]["total"] == 2
    assert any(role["name"] == "super_admin" for role in roles.json()["data"])

    role_change = await client.patch(
        f"/api/v1/admin/users/{second_id}/roles",
        headers=admin_headers,
        json={"roles": ["moderator"]},
    )
    assert role_change.status_code == 200
    assert role_change.json()["data"]["roles"] == ["moderator"]

    suspended = await client.patch(
        f"/api/v1/admin/users/{second_id}/status",
        headers=admin_headers,
        json={"status": "suspended", "reason": "Phase 7 automated moderation test"},
    )
    assert suspended.status_code == 200
    assert suspended.json()["data"]["status"] == "suspended"


async def test_homepage_builder_drives_public_home(
    client: AsyncClient, db: AsyncSession, admin_headers: dict[str, str]
) -> None:
    content = await published_content(db)
    section = await client.post(
        "/api/v1/admin/homepage/sections",
        headers=admin_headers,
        json={
            "key": "editors_choice",
            "title": "Editor's Choice",
            "algorithm": "manual",
            "presentation": "wide",
            "max_items": 8,
        },
    )
    assert section.status_code == 201, section.text
    section_id = section.json()["data"]["id"]
    assigned = await client.post(
        f"/api/v1/admin/homepage/sections/{section_id}/items",
        headers=admin_headers,
        json={"content_id": str(content.id), "sort_order": 0},
    )
    assert assigned.status_code == 201, assigned.text

    home = await client.get("/api/v1/home")
    assert home.status_code == 200
    sections = home.json()["data"]["sections"]
    assert sections[0]["id"] == "editors_choice"
    assert sections[0]["items"][0]["id"] == str(content.id)

    updated = await client.patch(
        f"/api/v1/admin/homepage/sections/{section_id}",
        headers=admin_headers,
        json={"title": "Tonight's Spotlight", "active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["active"] is False


async def test_notification_campaign_dispatch_is_idempotent_and_audited(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
    admin_headers: dict[str, str],
) -> None:
    campaign = await client.post(
        "/api/v1/admin/notification-campaigns",
        headers=admin_headers,
        json={
            "name": "Phase 7 launch",
            "type": "system",
            "title": "Drovixa control center is live",
            "body": "The administration platform is ready.",
            "audience": {"segment": "all"},
            "channels": ["in_app"],
        },
    )
    assert campaign.status_code == 201, campaign.text
    campaign_id = campaign.json()["data"]["id"]

    first = await client.post(
        f"/api/v1/admin/notification-campaigns/{campaign_id}/send",
        headers=admin_headers,
        json={"send_now": True},
    )
    second = await client.post(
        f"/api/v1/admin/notification-campaigns/{campaign_id}/send",
        headers=admin_headers,
        json={"send_now": True},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["data"]["status"] == "sent"

    user_id = UUID(str(registered["user"]["id"]))
    notifications = int(
        await db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user_id))
        or 0
    )
    assert notifications == 1

    logs = await client.get(
        "/api/v1/admin/audit-logs",
        headers=admin_headers,
        params={"entity_type": "notification_campaign"},
    )
    assert logs.status_code == 200
    assert logs.json()["meta"]["total"] >= 2
    assert (
        await db.scalar(select(func.count(AuditLog.id)).where(AuditLog.action.ilike("%campaign%")))
        or 0
    ) >= 2


async def test_admin_uploads_and_serves_durable_content_cover(
    client: AsyncClient, db: AsyncSession, admin_headers: dict[str, str]
) -> None:
    content = await published_content(db)
    image = b"\xff\xd8\xff\xe0" + b"drovixa-cover" * 20
    uploaded = await client.post(
        f"/api/v1/admin/content/{content.id}/media",
        params={"variant": "poster"},
        headers={
            **admin_headers,
            "Content-Type": "image/jpeg",
            "X-Public-API-Origin": "https://api.example.test",
        },
        content=image,
    )
    assert uploaded.status_code == 201, uploaded.text
    media_url = uploaded.json()["data"]["url"]
    assert media_url.startswith("https://api.example.test/api/v1/media/content/")
    saved = await client.get(f"/api/v1/admin/series/{content.id}", headers=admin_headers)
    assert saved.status_code == 200
    assert saved.json()["data"]["poster_url"] == media_url
    media_id = media_url.rsplit("/", 1)[-1]
    downloaded = await client.get(f"/api/v1/media/content/{media_id}")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "image/jpeg"
    assert downloaded.headers["cross-origin-resource-policy"] == "cross-origin"
    assert downloaded.content == image


async def test_admin_uploads_and_serves_real_subtitle_file(
    client: AsyncClient, db: AsyncSession, admin_headers: dict[str, str]
) -> None:
    content = await published_content(db)
    subtitle = b"WEBVTT\n\n00:00:01.000 --> 00:00:03.500\nBonjou Drovixa\n"
    uploaded = await client.post(
        f"/api/v1/admin/content/{content.id}/subtitle-file",
        params={"format": "vtt"},
        headers={
            **admin_headers,
            "Content-Type": "application/octet-stream",
            "X-Public-API-Origin": "https://api.example.test",
        },
        content=subtitle,
    )
    assert uploaded.status_code == 201, uploaded.text
    media_url = uploaded.json()["data"]["url"]
    media_id = media_url.rsplit("/", 1)[-1]
    downloaded = await client.get(f"/api/v1/media/content/{media_id}")
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"].startswith("text/vtt")
    assert downloaded.content == subtitle


async def test_admin_manages_user_coins_and_premium(
    client: AsyncClient, registered: dict[str, object], admin_headers: dict[str, str]
) -> None:
    user_id = registered["user"]["id"]
    plan = await client.post(
        "/api/v1/admin/subscription-plans",
        headers=admin_headers,
        json={
            "name": "Admin Premium",
            "slug": f"admin-premium-{uuid4().hex[:8]}",
            "interval": "monthly",
            "price": 9.99,
            "currency": "USD",
            "active": True,
        },
    )
    assert plan.status_code == 201, plan.text
    adjusted = await client.post(
        f"/api/v1/admin/wallets/{user_id}/adjust",
        headers={**admin_headers, "Idempotency-Key": "phase124-credit-001"},
        json={"amount": 250, "bonus_amount": 0, "reason": "Phase 12.4 verification"},
    )
    assert adjusted.status_code == 200, adjusted.text
    assert adjusted.json()["data"]["wallet"]["total_balance"] == 250
    granted = await client.post(
        f"/api/v1/admin/users/{user_id}/premium",
        headers=admin_headers,
        json={
            "plan_id": plan.json()["data"]["id"],
            "days": 1,
            "reason": "Phase 12.4 verification",
        },
    )
    assert granted.status_code == 200, granted.text
    assert granted.json()["data"]["provider"] == "admin_grant"
    first_end = granted.json()["data"]["current_period_end"]
    extended = await client.post(
        f"/api/v1/admin/users/{user_id}/premium",
        headers=admin_headers,
        json={"days": 4000, "reason": "Custom admin Premium duration"},
    )
    assert extended.status_code == 200, extended.text
    assert extended.json()["data"]["id"] == granted.json()["data"]["id"]
    assert extended.json()["data"]["plan"]["slug"] == "drovixa-internal-admin-premium"
    assert extended.json()["data"]["current_period_end"] > first_end
    overview = await client.get(
        f"/api/v1/admin/users/{user_id}/monetization", headers=admin_headers
    )
    assert overview.status_code == 200
    assert overview.json()["data"]["wallet"]["total_balance"] == 250
    assert overview.json()["data"]["subscription"]["status"] == "active"
    revoked = await client.post(
        f"/api/v1/admin/users/{user_id}/premium/revoke",
        headers=admin_headers,
        json={"reason": "Phase 12.4 verification complete"},
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["data"]["status"] == "cancelled"
