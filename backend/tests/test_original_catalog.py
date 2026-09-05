from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import Content, Episode, Season, Series, VideoAsset
from app.models.enums import (
    ContentStatus,
    ContentType,
    ContentVisibility,
    EpisodeAccessType,
    LedgerStatus,
    Orientation,
    SeriesStatus,
    VideoStatus,
    WalletTransactionType,
)
from app.models.monetization import EpisodeUnlock, WalletLedger
from app.models.user import User
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
    registered: dict[str, object],
) -> None:
    del registered
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
    await db.flush()
    former_series = Series(
        id=former_showcase.id,
        content=former_showcase,
        total_seasons=1,
        total_episodes=1,
        series_status=SeriesStatus.ONGOING,
        orientation=Orientation.VERTICAL,
    )
    former_season = Season(
        series=former_series,
        season_number=1,
        title="Former season",
        status=ContentStatus.PUBLISHED,
    )
    former_asset = VideoAsset(
        provider="drovixa_demo",
        provider_asset_id="showcase-v1:former-showcase:1",
        status=VideoStatus.READY,
        playback_id="vertical-01",
    )
    former_episode = Episode(
        series=former_series,
        season=former_season,
        episode_number=1,
        title="Former episode",
        video_asset=former_asset,
        orientation=Orientation.VERTICAL,
        access_type=EpisodeAccessType.COIN_UNLOCK,
        coin_price=10,
        status=ContentStatus.PUBLISHED,
    )
    db.add_all([former_series, former_season, former_asset, former_episode])
    await db.flush()
    user = await db.scalar(select(User).where(User.email == "viewer@example.com"))
    assert user is not None
    ledger = WalletLedger(
        user_id=user.id,
        type=WalletTransactionType.EPISODE_UNLOCK,
        amount=-10,
        balance_before=100,
        balance_after=90,
        coin_balance_before=100,
        coin_balance_after=90,
        bonus_balance_before=0,
        bonus_balance_after=0,
        reference=str(former_episode.id),
        source="showcase-test",
        status=LedgerStatus.COMPLETED,
        idempotency_key="showcase-unlock-regression",
        transaction_metadata={},
    )
    db.add(ledger)
    await db.flush()
    former_unlock = EpisodeUnlock(
        user_id=user.id,
        episode_id=former_episode.id,
        ledger_transaction_id=ledger.id,
        coin_price=10,
    )
    db.add(former_unlock)
    await db.commit()
    assert await sync_original_catalog(db) == 1
    assert await sync_original_catalog(db) == 1
    assert (
        await db.scalar(
            select(func.count(Content.id)).where(
                Content.demo_batch == SHOWCASE_BATCH,
                Content.deleted_at.is_(None),
            )
        )
        == 0
    )
    await db.refresh(former_showcase)
    assert former_showcase.deleted_at is not None
    assert former_showcase.status == ContentStatus.ARCHIVED
    assert former_showcase.visibility == ContentVisibility.PRIVATE
    await db.refresh(former_episode)
    await db.refresh(former_asset)
    assert former_episode.deleted_at is not None
    assert former_asset.deleted_at is not None
    assert await db.get(EpisodeUnlock, former_unlock.id) is not None
    assert await db.get(WalletLedger, ledger.id) is not None

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
