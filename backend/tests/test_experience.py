from __future__ import annotations

from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import utcnow
from app.models.content import Content, Episode, Series
from app.models.enums import (
    ContentStatus,
    ContentType,
    ContentVisibility,
    EpisodeAccessType,
    Orientation,
    SeriesStatus,
)
from app.models.experience import Notification


async def published_story(db: AsyncSession) -> tuple[Content, Episode]:
    content = Content(
        type=ContentType.SERIES,
        title="The Midnight Promise",
        slug=f"midnight-promise-{uuid4().hex[:8]}",
        short_description="A hidden promise changes two lives.",
        poster_url="https://images.example.test/poster.jpg",
        backdrop_url="https://images.example.test/backdrop.jpg",
        status=ContentStatus.PUBLISHED,
        visibility=ContentVisibility.PUBLIC,
        featured=True,
        premium=False,
        published_at=utcnow(),
        view_count=240,
        allowed_countries=[],
        blocked_countries=[],
    )
    series = Series(
        content=content,
        series_status=SeriesStatus.ONGOING,
        orientation=Orientation.VERTICAL,
        total_episodes=1,
    )
    episode = Episode(
        series=series,
        episode_number=1,
        title="The First Secret",
        thumbnail_url="https://images.example.test/episode.jpg",
        duration_seconds=75,
        access_type=EpisodeAccessType.FREE,
        orientation=Orientation.VERTICAL,
        status=ContentStatus.PUBLISHED,
        published_at=utcnow(),
    )
    db.add_all([content, series, episode])
    await db.commit()
    return content, episode


async def test_guest_home_discover_search_and_shorts(client: AsyncClient, db: AsyncSession) -> None:
    content, episode = await published_story(db)
    home = await client.get("/api/v1/home")
    assert home.status_code == 200, home.text
    assert home.json()["data"]["hero"][0]["id"] == str(content.id)
    discover = await client.get(
        "/api/v1/discover", params={"type": "series", "orientation": "vertical"}
    )
    assert discover.status_code == 200
    assert discover.json()["meta"]["total"] == 1
    search = await client.get("/api/v1/search", params={"q": "midnight"})
    assert search.json()["data"][0]["slug"] == content.slug
    shorts = await client.get("/api/v1/shorts")
    assert shorts.status_code == 200
    assert shorts.json()["data"][0]["id"] == str(episode.id)


async def test_favorites_search_history_and_notifications_require_user(
    client: AsyncClient, db: AsyncSession, registered: dict[str, object]
) -> None:
    content, _ = await published_story(db)
    headers = {"Authorization": f"Bearer {registered['access_token']}"}
    assert (await client.get("/api/v1/favorites")).status_code == 401
    assert (
        await client.post(f"/api/v1/favorites/{content.id}", headers=headers)
    ).status_code == 201
    favorites = await client.get("/api/v1/favorites", headers=headers)
    assert favorites.json()["data"][0]["is_favorite"] is True
    detail = await client.get(f"/api/v1/series/{content.slug}", headers=headers)
    assert detail.json()["data"]["is_favorite"] is True
    assert detail.json()["data"]["series_id"]
    assert (
        await client.post(
            "/api/v1/search/history", headers=headers, json={"query": " Midnight   Promise "}
        )
    ).status_code == 201
    assert (await client.get("/api/v1/search/suggestions", headers=headers)).json()["data"][
        "recent"
    ] == ["Midnight Promise"]
    user_id = UUID(str(registered["user"]["id"]))
    db.add(
        Notification(
            user_id=user_id,
            type="new_episode",
            title="New episode",
            body="The next chapter is ready.",
            payload={"content_id": str(content.id)},
        )
    )
    await db.commit()
    notifications = await client.get("/api/v1/notifications", headers=headers)
    assert notifications.json()["meta"]["unread"] == 1
    notification_id = notifications.json()["data"][0]["id"]
    assert (
        await client.patch(f"/api/v1/notifications/{notification_id}/read", headers=headers)
    ).status_code == 200
    preferences = await client.patch(
        "/api/v1/notification-preferences", headers=headers, json={"promotions": False}
    )
    assert preferences.json()["data"]["promotions"] is False
    assert preferences.json()["data"]["security"] is True
    assert (
        await client.delete(f"/api/v1/favorites/{content.id}", headers=headers)
    ).status_code == 200
