from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import utcnow
from app.models.configuration import FeatureFlag
from app.models.content import Content, Episode, Series
from app.models.enums import (
    ContentStatus,
    ContentType,
    ContentVisibility,
    EpisodeAccessType,
    Orientation,
    SeriesStatus,
)


async def published_story(db: AsyncSession) -> tuple[Content, Episode]:
    content = Content(
        type=ContentType.SERIES,
        title="Community Story",
        slug=f"community-story-{uuid4().hex[:8]}",
        status=ContentStatus.PUBLISHED,
        visibility=ContentVisibility.PUBLIC,
        published_at=utcnow(),
        allowed_countries=[],
        blocked_countries=[],
    )
    series = Series(
        content=content,
        series_status=SeriesStatus.ONGOING,
        orientation=Orientation.VERTICAL,
    )
    episode = Episode(
        series=series,
        episode_number=1,
        title="Community Episode",
        access_type=EpisodeAccessType.FREE,
        orientation=Orientation.VERTICAL,
        status=ContentStatus.PUBLISHED,
        published_at=utcnow(),
    )
    db.add_all([content, series, episode])
    await db.commit()
    return content, episode


async def enable_comments(db: AsyncSession) -> None:
    flag = await db.scalar(select(FeatureFlag).where(FeatureFlag.key == "comments_enabled"))
    assert flag is not None
    flag.enabled = True
    await db.commit()


async def test_comment_reply_like_edit_delete_flow(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
) -> None:
    await enable_comments(db)
    content, episode = await published_story(db)
    headers = {"Authorization": f"Bearer {registered['access_token']}"}

    created = await client.post(
        "/api/v1/comments",
        headers=headers,
        json={
            "target_type": "content",
            "target_id": str(content.id),
            "body": "A powerful first episode.",
            "is_spoiler": False,
        },
    )
    assert created.status_code == 201, created.text
    comment_id = created.json()["data"]["id"]

    listing = await client.get(
        "/api/v1/comments",
        params={"target_type": "content", "target_id": str(content.id)},
    )
    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] == 1

    reply = await client.post(
        "/api/v1/comments",
        headers=headers,
        json={
            "target_type": "content",
            "target_id": str(content.id),
            "parent_id": comment_id,
            "body": "I agree.",
        },
    )
    assert reply.status_code == 201, reply.text
    replies = await client.get(f"/api/v1/comments/{comment_id}/replies")
    assert replies.json()["meta"]["total"] == 1

    liked = await client.post(f"/api/v1/comments/{comment_id}/like", headers=headers)
    assert liked.json()["data"]["like_count"] == 1
    assert (await client.delete(f"/api/v1/comments/{comment_id}/like", headers=headers)).json()[
        "data"
    ]["like_count"] == 0

    content_like = await client.post(
        "/api/v1/likes",
        headers=headers,
        json={"target_type": "content", "target_id": str(content.id)},
    )
    assert content_like.status_code == 201
    assert content_like.json()["data"]["liked"] is True
    status_response = await client.get(
        "/api/v1/likes",
        headers=headers,
        params={"target_type": "content", "target_id": str(content.id)},
    )
    assert status_response.json()["data"] == {
        "target_type": "content",
        "target_id": str(content.id),
        "liked": True,
        "count": 1,
    }
    removed_like = await client.request(
        "DELETE",
        "/api/v1/likes",
        headers=headers,
        json={"target_type": "content", "target_id": str(content.id)},
    )
    assert removed_like.status_code == 200
    assert removed_like.json()["data"]["count"] == 0

    short_like = await client.post(
        "/api/v1/likes",
        headers=headers,
        json={"target_type": "short", "target_id": str(episode.id)},
    )
    assert short_like.status_code == 201

    edited = await client.patch(
        f"/api/v1/comments/{comment_id}",
        headers=headers,
        json={"body": "An unforgettable first episode.", "is_spoiler": True},
    )
    assert edited.json()["data"]["edited"] is True
    assert edited.json()["data"]["is_spoiler"] is True
    deleted = await client.delete(f"/api/v1/comments/{comment_id}", headers=headers)
    assert deleted.status_code == 200


async def test_comments_feature_flag_is_server_enforced(
    client: AsyncClient, db: AsyncSession, registered: dict[str, object]
) -> None:
    content, _ = await published_story(db)
    response = await client.post(
        "/api/v1/comments",
        headers={"Authorization": f"Bearer {registered['access_token']}"},
        json={
            "target_type": "content",
            "target_id": str(content.id),
            "body": "This must be blocked.",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "COMMENTS_DISABLED"


async def test_report_and_moderation_are_permission_protected(
    client: AsyncClient,
    db: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await enable_comments(db)
    content, _ = await published_story(db)
    viewer = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "reporter@example.com",
            "name": "Community Reporter",
            "password": "securepass123",
            "device": {
                "device_id": "device-reporter-12345",
                "name": "Reporter phone",
                "platform": "android",
            },
        },
    )
    assert viewer.status_code == 201
    user_headers = {"Authorization": f"Bearer {viewer.json()['data']['access_token']}"}
    created = await client.post(
        "/api/v1/comments",
        headers=user_headers,
        json={
            "target_type": "content",
            "target_id": str(content.id),
            "body": "Please moderate this.",
        },
    )
    comment_id = created.json()["data"]["id"]
    report = await client.post(
        f"/api/v1/comments/{comment_id}/report",
        headers=user_headers,
        json={"reason_code": "inappropriate", "details": "Needs review"},
    )
    assert report.status_code == 201, report.text
    assert report.json()["data"]["created"] is True

    assert (await client.get("/api/v1/admin/reports", headers=user_headers)).status_code == 403
    reports = await client.get("/api/v1/admin/reports", headers=admin_headers)
    assert reports.status_code == 200
    report_id = reports.json()["data"][0]["id"]
    resolved = await client.patch(
        f"/api/v1/admin/reports/{report_id}",
        headers=admin_headers,
        json={"status": "resolved", "resolution_note": "Reviewed"},
    )
    assert resolved.json()["data"]["status"] == "resolved"

    hidden = await client.patch(
        f"/api/v1/admin/comments/{comment_id}",
        headers=admin_headers,
        json={"action": "hide", "reason": "Community guidelines"},
    )
    assert hidden.status_code == 200
    assert hidden.json()["data"]["status"] == "hidden"
    restored = await client.patch(
        f"/api/v1/admin/comments/{comment_id}",
        headers=admin_headers,
        json={"action": "restore", "reason": "Appeal accepted"},
    )
    assert restored.json()["data"]["status"] == "visible"


async def test_mute_blocks_new_comments(
    client: AsyncClient,
    db: AsyncSession,
    admin_headers: dict[str, str],
) -> None:
    await enable_comments(db)
    content, _ = await published_story(db)
    second_payload = {
        "email": "second-viewer@example.com",
        "name": "Second Viewer",
        "password": "securepass123",
        "device": {
            "device_id": "device-second-12345",
            "name": "Second phone",
            "platform": "android",
        },
    }
    second = await client.post("/api/v1/auth/register", json=second_payload)
    assert second.status_code == 201
    second_data = second.json()["data"]
    second_headers = {"Authorization": f"Bearer {second_data['access_token']}"}
    user_id = second_data["user"]["id"]

    muted = await client.post(
        f"/api/v1/admin/users/{user_id}/mute",
        headers=admin_headers,
        json={"reason": "Repeated spam"},
    )
    assert muted.status_code == 201
    blocked = await client.post(
        "/api/v1/comments",
        headers=second_headers,
        json={
            "target_type": "content",
            "target_id": str(content.id),
            "body": "This should not be posted.",
        },
    )
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "COMMUNITY_MUTED"
