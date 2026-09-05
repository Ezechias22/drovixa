from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content, Episode, VideoAsset
from app.models.enums import ContentStatus, ContentType, ContentVisibility, EpisodeAccessType
from app.scripts.demo_catalog import (
    DEMO_BATCH,
    LANGUAGES,
    SERIES,
    remove_demo_catalog,
    sync_demo_catalog,
)


async def test_showcase_is_idempotent_localized_and_playable(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    assert await sync_demo_catalog(db) == 15
    assert await sync_demo_catalog(db) == 15
    assert (
        await db.scalar(select(func.count(Content.id)).where(Content.demo_batch == DEMO_BATCH))
        == 15
    )
    assert (
        await db.scalar(
            select(func.count(Episode.id))
            .join(Content, Episode.series_id == Content.id)
            .where(Content.demo_batch == DEMO_BATCH)
        )
        == 30
    )
    demo_content = list(
        await db.scalars(select(Content).where(Content.demo_batch == DEMO_BATCH))
    )
    demo_episodes = list(
        await db.scalars(
            select(Episode)
            .join(Content, Episode.series_id == Content.id)
            .where(Content.demo_batch == DEMO_BATCH)
        )
    )
    assert all(set(row.translations) == set(LANGUAGES) for row in demo_content)
    assert all(set(row.translations) == set(LANGUAGES) for row in demo_episodes)

    expected_titles = {language: title for language, (title, _) in SERIES[0]["copy"].items()}
    for language, expected in expected_titles.items():
        response = await client.get(
            "/api/v1/series/midnight-in-jacmel",
            headers={"X-Drovixa-Language": language},
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["title"] == expected

    detail = (
        await client.get(
            "/api/v1/series/midnight-in-jacmel",
            headers={"X-Drovixa-Language": "ht"},
        )
    ).json()["data"]
    episodes = (
        await client.get(
            f"/api/v1/series/{detail['id']}/episodes",
            headers={"X-Drovixa-Language": "fr"},
        )
    ).json()["data"]
    assert len(episodes) == 2
    assert episodes[0]["title"].startswith("Épisode 1")
    assert episodes[0]["access_type"] == EpisodeAccessType.FREE
    assert episodes[0]["coin_price"] == 0
    assert episodes[0]["unlocked"] is True
    assert episodes[1]["access_type"] == EpisodeAccessType.COIN_UNLOCK
    assert episodes[1]["coin_price"] == 10
    assert episodes[1]["unlocked"] is False

    playback = await client.post(
        f"/api/v1/playback/episodes/{episodes[0]['id']}/authorize",
        json={"client_device_id": "showcase-test-device"},
        headers={"X-Drovixa-Language": "ht"},
    )
    assert playback.status_code == 200, playback.text
    grant = playback.json()["data"]
    assert grant["content_title"] == "Minwi nan Jakmèl"
    assert grant["hls_url"].endswith("/video/horizontal-01/index.m3u8")

    manifest = await client.get("/api/v1/demo-media/video/horizontal-01/index.m3u8")
    assert manifest.status_code == 200
    assert "#EXTM3U" in manifest.text


async def test_showcase_removal_does_not_touch_owner_content(db: AsyncSession) -> None:
    await sync_demo_catalog(db)
    owner_content = Content(
        id=uuid4(),
        type=ContentType.SERIES,
        title="Owner Series",
        slug=f"owner-series-{uuid4().hex[:8]}",
        status=ContentStatus.PUBLISHED,
        visibility=ContentVisibility.PUBLIC,
        allowed_countries=[],
        blocked_countries=[],
    )
    db.add(owner_content)
    await db.commit()

    assert await remove_demo_catalog(db) == 15
    await db.commit()
    assert await db.get(Content, owner_content.id) is not None
    assert (
        await db.scalar(select(func.count(Content.id)).where(Content.demo_batch == DEMO_BATCH)) == 0
    )
    assert (
        await db.scalar(
            select(func.count(VideoAsset.id)).where(VideoAsset.provider == "drovixa_demo")
        )
        == 0
    )
