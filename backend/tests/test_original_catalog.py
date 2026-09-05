from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content, Episode, VideoAsset
from app.models.enums import (
    ContentStatus,
    ContentType,
    ContentVisibility,
    EpisodeAccessType,
    Orientation,
)
from app.scripts.original_catalog import (
    LANGUAGES,
    ORIGINAL_PROVIDER,
    ORIGINAL_SLUG,
    SHOWCASE_BATCH,
    stable_id,
    sync_original_catalog,
)


async def test_original_replaces_showcase_and_is_idempotent(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    former_showcase = Content(
        type=ContentType.SERIES,
        title="Former showcase",
        slug="former-showcase",
        demo_batch=SHOWCASE_BATCH,
        status=ContentStatus.PUBLISHED,
        visibility=ContentVisibility.PUBLIC,
        allowed_countries=[],
        blocked_countries=[],
    )
    db.add(former_showcase)
    await db.commit()
    assert await sync_original_catalog(db) == 1
    assert await sync_original_catalog(db) == 1
    assert (
        await db.scalar(
            select(func.count(Content.id)).where(Content.demo_batch == SHOWCASE_BATCH)
        )
        == 0
    )

    content = await db.get(Content, stable_id("content", ORIGINAL_SLUG))
    assert content is not None
    assert content.demo_batch is None
    assert content.featured is True
    assert set(content.translations) == set(LANGUAGES)

    detail = (
        await client.get(
            f"/api/v1/series/{ORIGINAL_SLUG}",
            headers={"X-Drovixa-Language": "ht"},
        )
    ).json()["data"]
    assert detail["title"] == "Minwi nan Jakmèl"
    assert detail["orientation"] == Orientation.VERTICAL

    episodes_response = await client.get(
        f"/api/v1/series/{detail['id']}/episodes",
        headers={"X-Drovixa-Language": "fr"},
    )
    assert episodes_response.status_code == 200, episodes_response.text
    episodes = episodes_response.json()["data"]
    assert len(episodes) == 1
    assert episodes[0]["title"] == "Épisode 1 · Le signal de minuit"
    assert episodes[0]["access_type"] == EpisodeAccessType.FREE
    assert episodes[0]["coin_price"] == 0
    assert episodes[0]["unlocked"] is True

    asset = await db.scalar(select(VideoAsset).where(VideoAsset.provider == ORIGINAL_PROVIDER))
    assert asset is not None
    assert asset.playback_id == "minwi-nan-jakmel-ep01"
    assert asset.height > asset.width

    playback = await client.post(
        f"/api/v1/playback/episodes/{episodes[0]['id']}/authorize",
        json={"client_device_id": "original-test-device"},
        headers={"X-Drovixa-Language": "ht"},
    )
    assert playback.status_code == 200, playback.text
    grant = playback.json()["data"]
    assert grant["content_title"] == "Minwi nan Jakmèl"
    assert grant["hls_url"].endswith(
        "/original-media/video/minwi-nan-jakmel-ep01/index.m3u8"
    )

    manifest = await client.get(
        "/api/v1/original-media/video/minwi-nan-jakmel-ep01/index.m3u8"
    )
    assert manifest.status_code == 200
    assert "#EXTM3U" in manifest.text
    assert "#EXT-X-ENDLIST" in manifest.text

    first_segment = await client.get(
        "/api/v1/original-media/video/minwi-nan-jakmel-ep01/segment-000.ts"
    )
    assert first_segment.status_code == 200
    assert first_segment.content.startswith(b"\x47")


async def test_original_catalog_has_one_episode(db: AsyncSession) -> None:
    await sync_original_catalog(db)
    count = await db.scalar(
        select(func.count(Episode.id)).where(
            Episode.series_id == stable_id("content", ORIGINAL_SLUG)
        )
    )
    assert count == 1
