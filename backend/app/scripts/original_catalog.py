from __future__ import annotations

import argparse
import asyncio
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid5

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionFactory, dispose_database
from app.models.base import utcnow
from app.models.catalog import Country, Genre, Language
from app.models.content import Content, Episode, Season, Series, VideoAsset
from app.models.enums import (
    AgeRating,
    ContentStatus,
    ContentType,
    ContentVisibility,
    EpisodeAccessType,
    Orientation,
    SeriesStatus,
    VideoStatus,
)

ORIGINAL_PROVIDER = "drovixa_original"
ORIGINAL_SLUG = "minwi-nan-jakmel"
SHOWCASE_BATCH = "showcase-v1"
NAMESPACE = UUID("996dc2e2-03c5-4b51-a221-2bea45abca76")
LANGUAGES = ("ht", "fr", "en", "es", "pt-BR")

SERIES_COPY = {
    "ht": {
        "title": "Minwi nan Jakmèl",
        "short_description": (
            "Yon atis mural ak yon animatè radyo dekouvri yon siyal misterye "
            "ki reveye yon sekrè nan kè Jakmèl."
        ),
        "description": (
            "Amara Delva ap fini yon mural lè yon ansyen radyo rele l egzakteman "
            "a minwi. Avèk Malik Saint-Fleur, li suiv limyè ble a nan lari Jakmèl "
            "yo, kote chak frekans ap revele yon pati nan yon verite yo te antere."
        ),
    },
    "fr": {
        "title": "Minuit à Jacmel",
        "short_description": (
            "Une muraliste et un animateur radio découvrent un signal mystérieux "
            "qui réveille un secret au cœur de Jacmel."
        ),
        "description": (
            "Amara Delva termine une fresque lorsqu'une vieille radio l'appelle à "
            "minuit précis. Avec Malik Saint-Fleur, elle suit la lumière bleue dans "
            "les rues de Jacmel, où chaque fréquence révèle une vérité enfouie."
        ),
    },
    "en": {
        "title": "Midnight in Jacmel",
        "short_description": (
            "A muralist and a radio host discover a mysterious signal awakening a "
            "secret in the heart of Jacmel."
        ),
        "description": (
            "Amara Delva is finishing a mural when an old radio calls to her at "
            "exactly midnight. With Malik Saint-Fleur, she follows the blue light "
            "through Jacmel, where every frequency reveals a buried truth."
        ),
    },
    "es": {
        "title": "Medianoche en Jacmel",
        "short_description": (
            "Una muralista y un locutor descubren una señal misteriosa que despierta "
            "un secreto en el corazón de Jacmel."
        ),
        "description": (
            "Amara Delva termina un mural cuando una radio antigua la llama justo a "
            "medianoche. Junto a Malik Saint-Fleur, sigue la luz azul por Jacmel, "
            "donde cada frecuencia revela una verdad enterrada."
        ),
    },
    "pt-BR": {
        "title": "Meia-noite em Jacmel",
        "short_description": (
            "Uma muralista e um radialista descobrem um sinal misterioso que desperta "
            "um segredo no coração de Jacmel."
        ),
        "description": (
            "Amara Delva termina um mural quando um rádio antigo a chama exatamente à "
            "meia-noite. Com Malik Saint-Fleur, ela segue a luz azul por Jacmel, onde "
            "cada frequência revela uma verdade enterrada."
        ),
    },
}

EPISODE_COPY = {
    "ht": {
        "title": "Epizòd 1 · Siyal Minwi a",
        "description": (
            "Yon frekans enposib mennen Amara ak Malik soti bò mural la rive nan "
            "yon ansyen chapèl, pandan yon etranje ap suiv chak mouvman yo."
        ),
    },
    "fr": {
        "title": "Épisode 1 · Le signal de minuit",
        "description": (
            "Une fréquence impossible conduit Amara et Malik de la fresque à une "
            "ancienne chapelle, tandis qu'un inconnu surveille leurs mouvements."
        ),
    },
    "en": {
        "title": "Episode 1 · The Midnight Signal",
        "description": (
            "An impossible frequency leads Amara and Malik from the mural to an old "
            "chapel while a stranger tracks their every move."
        ),
    },
    "es": {
        "title": "Episodio 1 · La señal de medianoche",
        "description": (
            "Una frecuencia imposible lleva a Amara y Malik desde el mural hasta una "
            "antigua capilla, mientras un desconocido sigue sus movimientos."
        ),
    },
    "pt-BR": {
        "title": "Episódio 1 · O sinal da meia-noite",
        "description": (
            "Uma frequência impossível leva Amara e Malik do mural a uma antiga "
            "capela, enquanto um desconhecido acompanha cada movimento deles."
        ),
    },
}


def stable_id(*parts: object) -> UUID:
    return uuid5(NAMESPACE, ":".join(str(part) for part in parts))


def series_translations() -> dict[str, dict[str, str]]:
    return {
        language: {
            **copy,
            "seo_title": f"{copy['title']} | Drovixa Original",
            "seo_description": copy["short_description"],
        }
        for language, copy in SERIES_COPY.items()
    }


async def remove_original_catalog(db: AsyncSession) -> int:
    content_id = stable_id("content", ORIGINAL_SLUG)
    if await db.get(Content, content_id) is None:
        return 0
    asset_ids = list(
        await db.scalars(
            select(Episode.video_asset_id).where(
                Episode.series_id == content_id,
                Episode.video_asset_id.is_not(None),
            )
        )
    )
    await db.execute(delete(Content).where(Content.id == content_id))
    await db.flush()
    if asset_ids:
        await db.execute(delete(VideoAsset).where(VideoAsset.id.in_(asset_ids)))
    return 1


async def remove_showcase_catalog(db: AsyncSession) -> int:
    """Archive only the former showcase batch while preserving coin-ledger history."""
    content_ids = list(
        await db.scalars(select(Content.id).where(Content.demo_batch == SHOWCASE_BATCH))
    )
    if not content_ids:
        return 0
    asset_ids = list(
        await db.scalars(
            select(Episode.video_asset_id).where(
                Episode.series_id.in_(content_ids),
                Episode.video_asset_id.is_not(None),
            )
        )
    )
    archived_at = utcnow()
    await db.execute(
        update(Episode)
        .where(Episode.series_id.in_(content_ids))
        .values(
            status=ContentStatus.ARCHIVED,
            deleted_at=archived_at,
        )
    )
    await db.execute(
        update(Season)
        .where(Season.series_id.in_(content_ids))
        .values(
            status=ContentStatus.ARCHIVED,
            deleted_at=archived_at,
        )
    )
    if asset_ids:
        await db.execute(
            update(VideoAsset)
            .where(VideoAsset.id.in_(asset_ids))
            .values(
                status=VideoStatus.DELETED,
                deleted_at=archived_at,
            )
        )
    await db.execute(
        update(Content)
        .where(Content.id.in_(content_ids))
        .values(
            status=ContentStatus.ARCHIVED,
            visibility=ContentVisibility.PRIVATE,
            featured=False,
            deleted_at=archived_at,
        )
    )
    return len(content_ids)


async def sync_original_catalog(db: AsyncSession) -> int:
    await remove_showcase_catalog(db)
    settings = get_settings()
    if not settings.ORIGINAL_CATALOG_ENABLED:
        removed = await remove_original_catalog(db)
        await db.commit()
        return -removed

    base_url = settings.ORIGINAL_MEDIA_BASE_URL.rstrip("/")
    languages = {row.code: row for row in await db.scalars(select(Language))}
    countries = {row.code: row for row in await db.scalars(select(Country))}
    genres = {row.slug: row for row in await db.scalars(select(Genre))}
    now = utcnow()

    content_id = stable_id("content", ORIGINAL_SLUG)
    content = await db.get(Content, content_id)
    if content is None:
        slug_owner = await db.scalar(select(Content).where(Content.slug == ORIGINAL_SLUG))
        if slug_owner is not None:
            raise RuntimeError(
                f"Cannot publish {ORIGINAL_SLUG}: another catalog item already owns the slug."
            )
        content = Content(
            id=content_id,
            type=ContentType.SERIES,
            title=SERIES_COPY["en"]["title"],
            slug=ORIGINAL_SLUG,
        )
        db.add(content)

    localized = series_translations()
    english = localized["en"]
    content.type = ContentType.SERIES
    content.title = english["title"]
    content.original_title = localized["ht"]["title"]
    content.slug = ORIGINAL_SLUG
    content.short_description = english["short_description"]
    content.description = english["description"]
    content.translations = localized
    content.demo_batch = None
    content.poster_url = f"{base_url}/posters/minwi-nan-jakmel.jpg"
    content.backdrop_url = f"{base_url}/backdrops/minwi-nan-jakmel.jpg"
    content.release_date = date(2026, 9, 5)
    content.country = countries.get("HT")
    content.original_language = languages.get("ht")
    content.age_rating = AgeRating.THIRTEEN_PLUS
    content.status = ContentStatus.PUBLISHED
    content.visibility = ContentVisibility.PUBLIC
    content.featured = True
    content.premium = False
    content.rating = Decimal("0")
    content.rating_count = 0
    content.view_count = 0
    content.like_count = 0
    content.allowed_countries = []
    content.blocked_countries = []
    content.seo_title = english["seo_title"]
    content.seo_description = english["seo_description"]
    content.published_at = now
    content.deleted_at = None
    content.genres = [genres[slug] for slug in ("mystery", "romance") if slug in genres]

    series = await db.get(Series, content_id)
    if series is None:
        series = Series(id=content_id, content=content)
        db.add(series)
    series.total_seasons = 1
    series.total_episodes = 1
    series.series_status = SeriesStatus.ONGOING
    series.orientation = Orientation.VERTICAL

    season_id = stable_id("season", ORIGINAL_SLUG, 1)
    season = await db.get(Season, season_id)
    if season is None:
        season = Season(id=season_id, series=series, season_number=1)
        db.add(season)
    season.series = series
    season.season_number = 1
    season.title = "Sezon 1"
    season.description = "Premye sezon Drovixa Original Minwi nan Jakmèl."
    season.poster_url = content.poster_url
    season.release_date = content.release_date
    season.status = ContentStatus.PUBLISHED
    season.sort_order = 1
    season.deleted_at = None

    asset_id = stable_id("asset", ORIGINAL_SLUG, 1)
    asset = await db.get(VideoAsset, asset_id)
    if asset is None:
        asset = VideoAsset(
            id=asset_id,
            provider=ORIGINAL_PROVIDER,
            provider_asset_id="drovixa-original:minwi-nan-jakmel:episode-1:v1",
        )
        db.add(asset)
    asset.provider = ORIGINAL_PROVIDER
    asset.provider_asset_id = "drovixa-original:minwi-nan-jakmel:episode-1:v1"
    asset.status = VideoStatus.READY
    asset.duration_seconds = 121
    asset.width = 720
    asset.height = 1280
    asset.aspect_ratio = "9:16"
    asset.thumbnail_url = f"{base_url}/thumbnails/minwi-nan-jakmel-ep01.jpg"
    asset.playback_id = "minwi-nan-jakmel-ep01"
    asset.ready_at = now
    asset.asset_metadata = {
        "collection": "drovixa-originals",
        "copyright_owner": "Drovixa",
        "orientation": "vertical",
        "bundled": True,
    }
    asset.deleted_at = None

    episode_id = stable_id("episode", ORIGINAL_SLUG, 1)
    episode = await db.get(Episode, episode_id)
    if episode is None:
        episode = Episode(
            id=episode_id,
            series=series,
            season=season,
            episode_number=1,
            title=EPISODE_COPY["en"]["title"],
        )
        db.add(episode)
    episode.series = series
    episode.season = season
    episode.episode_number = 1
    episode.title = EPISODE_COPY["en"]["title"]
    episode.description = EPISODE_COPY["en"]["description"]
    episode.translations = EPISODE_COPY
    episode.thumbnail_url = asset.thumbnail_url
    episode.duration_seconds = 121
    episode.video_asset = asset
    episode.orientation = Orientation.VERTICAL
    episode.access_type = EpisodeAccessType.FREE
    episode.coin_price = 0
    episode.premium = False
    episode.free_from = None
    episode.free_until = None
    episode.published_at = now
    episode.status = ContentStatus.PUBLISHED
    episode.sort_order = 1
    episode.deleted_at = None

    await db.commit()
    return 1


async def run(action: str) -> None:
    async with SessionFactory() as db:
        if action in {"sync", "publish"}:
            count = await sync_original_catalog(db)
            if count < 0:
                print(f"Drovixa Originals disabled: {-count} series removed.")
            else:
                print("Drovixa Originals ready: 1 series, 1 full episode.")
        else:
            count = await remove_original_catalog(db)
            await db.commit()
            print(f"Drovixa Originals removed: {count} series.")
    await dispose_database()


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish Drovixa Original productions.")
    parser.add_argument("action", choices=("sync", "publish", "remove"), nargs="?", default="sync")
    args = parser.parse_args()
    asyncio.run(run(args.action))


if __name__ == "__main__":
    main()
