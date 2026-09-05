from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.localization import localized_fields
from app.models.base import utcnow
from app.models.catalog import Actor, Country, CrewMember, Genre, Language, Tag
from app.models.content import (
    Content,
    ContentActor,
    ContentCrew,
    Episode,
    Movie,
    Season,
    Series,
    Subtitle,
    VideoAsset,
)
from app.models.enums import (
    ContentStatus,
    ContentType,
    ContentVisibility,
    VideoStatus,
)
from app.schemas.content import MovieCreate, MovieUpdate, SeriesCreate, SeriesUpdate
from app.services.catalog import ensure_unique, require_reference, slugify

RELATION_FIELDS = {"genre_ids", "tag_ids", "actor_credits", "crew_credits"}
SERIES_FIELDS = {"series_status", "orientation"}
MOVIE_FIELDS = {"duration_seconds", "video_asset_id", "access_type", "coin_price"}


async def get_entity[EntityT: Season | Episode | VideoAsset | Subtitle](
    db: AsyncSession, model: type[EntityT], entity_id: UUID, *, label: str
) -> EntityT:
    row = await db.scalar(select(model).where(model.id == entity_id, model.deleted_at.is_(None)))
    if row is None:
        raise AppError("NOT_FOUND", f"The {label} was not found.", status_code=404)
    return row


async def get_series(db: AsyncSession, series_id: UUID) -> Series:
    row = await db.scalar(
        select(Series)
        .join(Series.content)
        .where(Series.id == series_id, Content.deleted_at.is_(None))
    )
    if row is None:
        raise AppError("NOT_FOUND", "The series was not found.", status_code=404)
    return row


async def get_movie(db: AsyncSession, movie_id: UUID) -> Movie:
    row = await db.scalar(
        select(Movie).join(Movie.content).where(Movie.id == movie_id, Content.deleted_at.is_(None))
    )
    if row is None:
        raise AppError("NOT_FOUND", "The movie was not found.", status_code=404)
    return row


async def get_content_by_slug(db: AsyncSession, slug: str, *, public_only: bool) -> Content:
    statement = select(Content).where(Content.slug == slug, Content.deleted_at.is_(None))
    if public_only:
        now = utcnow()
        statement = statement.where(
            Content.status == ContentStatus.PUBLISHED,
            Content.visibility == ContentVisibility.PUBLIC,
            or_(Content.published_at.is_(None), Content.published_at <= now),
            or_(Content.license_start.is_(None), Content.license_start <= now),
            or_(Content.license_end.is_(None), Content.license_end >= now),
        )
    row = await db.scalar(statement)
    if row is None:
        raise AppError("NOT_FOUND", "The content was not found.", status_code=404)
    return row


async def list_content(
    db: AsyncSession,
    *,
    content_type: ContentType,
    page: int,
    limit: int,
    public_only: bool,
) -> tuple[list[Content], int]:
    conditions = [Content.type == content_type, Content.deleted_at.is_(None)]
    if public_only:
        now = utcnow()
        conditions.extend(
            [
                Content.status == ContentStatus.PUBLISHED,
                Content.visibility == ContentVisibility.PUBLIC,
                or_(Content.published_at.is_(None), Content.published_at <= now),
                or_(Content.license_start.is_(None), Content.license_start <= now),
                or_(Content.license_end.is_(None), Content.license_end >= now),
            ]
        )
    statement = select(Content).where(*conditions)
    total = int(await db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = (
        await db.scalars(
            statement.order_by(Content.published_at.desc(), Content.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()
    return list(rows), total


async def _references(db: AsyncSession, model: type[Any], ids: list[UUID]) -> list[Any]:
    if len(ids) != len(set(ids)):
        raise AppError("VALIDATION_ERROR", "Reference IDs must be unique.", status_code=422)
    if not ids:
        return []
    rows = (
        await db.scalars(select(model).where(model.id.in_(ids), model.deleted_at.is_(None)))
    ).all()
    if len(rows) != len(ids):
        raise AppError("VALIDATION_ERROR", "One or more references do not exist.", status_code=422)
    by_id = {row.id: row for row in rows}
    return [by_id[item_id] for item_id in ids]


async def _apply_relations(db: AsyncSession, row: Content, data: dict[str, Any]) -> None:
    if "genre_ids" in data:
        row.genres = await _references(db, Genre, data["genre_ids"] or [])
    if "tag_ids" in data:
        row.tags = await _references(db, Tag, data["tag_ids"] or [])
    if "actor_credits" in data:
        credit_values = data["actor_credits"] or []
        actor_ids = list(dict.fromkeys(credit["actor_id"] for credit in credit_values))
        actors = await _references(db, Actor, actor_ids)
        actor_map = {actor.id: actor for actor in actors}
        row.actor_credits = [
            ContentActor(actor=actor_map[credit.pop("actor_id")], **credit)
            for credit in credit_values
        ]
    if "crew_credits" in data:
        credit_values = data["crew_credits"] or []
        member_ids = list(dict.fromkeys(credit["crew_member_id"] for credit in credit_values))
        members = await _references(db, CrewMember, member_ids)
        member_map = {member.id: member for member in members}
        row.crew_credits = [
            ContentCrew(crew_member=member_map[credit.pop("crew_member_id")], **credit)
            for credit in credit_values
        ]


async def _validate_common_references(db: AsyncSession, data: dict[str, Any]) -> None:
    await require_reference(db, Country, data.get("country_id"), label="country")
    await require_reference(db, Language, data.get("original_language_id"), label="language")


async def _create_common(
    db: AsyncSession, payload: SeriesCreate | MovieCreate, content_type: ContentType
) -> Content:
    data = payload.model_dump(mode="python")
    relation_data = {key: data.pop(key) for key in RELATION_FIELDS}
    subtype_fields = SERIES_FIELDS if content_type == ContentType.SERIES else MOVIE_FIELDS
    for field in subtype_fields:
        data.pop(field, None)
    country = await require_reference(db, Country, data.get("country_id"), label="country")
    language = await require_reference(
        db, Language, data.get("original_language_id"), label="language"
    )
    data["slug"] = slugify(data.get("slug") or data["title"])
    await ensure_unique(db, Content, "slug", data["slug"])
    row = Content(type=content_type, status=ContentStatus.DRAFT, **data)
    row.country = country
    row.original_language = language
    db.add(row)
    await _apply_relations(db, row, relation_data)
    return row


async def create_series(db: AsyncSession, payload: SeriesCreate) -> Series:
    content = await _create_common(db, payload, ContentType.SERIES)
    row = Series(
        content=content,
        series_status=payload.series_status,
        orientation=payload.orientation,
    )
    db.add(row)
    await db.flush()
    return row


async def create_movie(db: AsyncSession, payload: MovieCreate) -> Movie:
    asset = None
    if payload.video_asset_id is not None:
        asset = await get_entity(db, VideoAsset, payload.video_asset_id, label="video asset")
    content = await _create_common(db, payload, ContentType.MOVIE)
    row = Movie(
        content=content,
        duration_seconds=payload.duration_seconds,
        video_asset_id=payload.video_asset_id,
        access_type=payload.access_type,
        coin_price=payload.coin_price,
        video_asset=asset,
    )
    db.add(row)
    await db.flush()
    return row


def _validate_rights(row: Content, changes: dict[str, Any]) -> None:
    start = changes.get("license_start", row.license_start)
    end = changes.get("license_end", row.license_end)
    allowed = changes.get("allowed_countries", row.allowed_countries)
    blocked = changes.get("blocked_countries", row.blocked_countries)
    if start and end and end < start:
        raise AppError(
            "VALIDATION_ERROR", "license_end must follow license_start.", status_code=422
        )
    if set(allowed or []) & set(blocked or []):
        raise AppError("VALIDATION_ERROR", "Country rights lists cannot overlap.", status_code=422)


async def _update_common(
    db: AsyncSession, row: Content, payload: SeriesUpdate | MovieUpdate
) -> dict[str, Any]:
    data = payload.model_dump(mode="python", exclude_unset=True)
    relations = {key: data.pop(key) for key in RELATION_FIELDS if key in data}
    for field in SERIES_FIELDS | MOVIE_FIELDS:
        data.pop(field, None)
    await _validate_common_references(db, data)
    if "country_id" in data:
        row.country = await require_reference(db, Country, data["country_id"], label="country")
    if "original_language_id" in data:
        row.original_language = await require_reference(
            db, Language, data["original_language_id"], label="language"
        )
    if "slug" in data and data["slug"] is not None:
        data["slug"] = slugify(data["slug"])
        await ensure_unique(db, Content, "slug", data["slug"], exclude_id=row.id)
    _validate_rights(row, data)
    for field, value in data.items():
        setattr(row, field, value)
    await _apply_relations(db, row, relations)
    return payload.model_dump(mode="python", exclude_unset=True)


async def update_series(db: AsyncSession, row: Series, payload: SeriesUpdate) -> Series:
    data = await _update_common(db, row.content, payload)
    for field in SERIES_FIELDS:
        if field in data:
            setattr(row, field, data[field])
    await db.flush()
    return row


async def update_movie(db: AsyncSession, row: Movie, payload: MovieUpdate) -> Movie:
    data = await _update_common(db, row.content, payload)
    if "video_asset_id" in data:
        row.video_asset = (
            await get_entity(db, VideoAsset, data["video_asset_id"], label="video asset")
            if data["video_asset_id"] is not None
            else None
        )
    access = data.get("access_type", row.access_type)
    price = data.get("coin_price", row.coin_price)
    if access.value in {"coin_unlock", "premium_or_coin"} and price < 1:
        raise AppError(
            "VALIDATION_ERROR",
            "coin_price must be positive for coin access.",
            status_code=422,
        )
    for field in MOVIE_FIELDS:
        if field in data:
            setattr(row, field, data[field])
    await db.flush()
    return row


async def publish_content(db: AsyncSession, row: Series | Movie) -> None:
    content = row.content
    if isinstance(row, Movie):
        if row.video_asset is None or row.video_asset.status != VideoStatus.READY:
            raise AppError("VIDEO_NOT_READY", "The movie video is not ready.", status_code=409)
    content.status = ContentStatus.PUBLISHED
    content.visibility = ContentVisibility.PUBLIC
    content.published_at = content.published_at or utcnow()
    await db.flush()


async def archive_content(db: AsyncSession, row: Series | Movie) -> None:
    row.content.status = ContentStatus.ARCHIVED
    row.content.visibility = ContentVisibility.PRIVATE
    row.content.deleted_at = utcnow()
    await db.flush()


async def refresh_series_totals(db: AsyncSession, series: Series) -> None:
    series.total_seasons = int(
        await db.scalar(
            select(func.count(Season.id)).where(
                Season.series_id == series.id, Season.deleted_at.is_(None)
            )
        )
        or 0
    )
    series.total_episodes = int(
        await db.scalar(
            select(func.count(Episode.id)).where(
                Episode.series_id == series.id, Episode.deleted_at.is_(None)
            )
        )
        or 0
    )


async def validate_episode_links(
    db: AsyncSession,
    *,
    series_id: UUID,
    season_id: UUID | None,
    video_asset_id: UUID | None,
) -> None:
    await get_series(db, series_id)
    if season_id is not None:
        season = await get_entity(db, Season, season_id, label="season")
        if season.series_id != series_id:
            raise AppError(
                "VALIDATION_ERROR",
                "The season does not belong to the series.",
                status_code=422,
            )
    if video_asset_id is not None:
        await get_entity(db, VideoAsset, video_asset_id, label="video asset")


async def publish_episode(db: AsyncSession, row: Episode) -> None:
    if row.video_asset is None or row.video_asset.status != VideoStatus.READY:
        raise AppError("VIDEO_NOT_READY", "The episode video is not ready.", status_code=409)
    row.status = ContentStatus.PUBLISHED
    row.published_at = row.published_at or utcnow()
    await db.flush()


async def publish_season(db: AsyncSession, row: Season) -> None:
    row.status = ContentStatus.PUBLISHED
    await db.flush()


def country_data(row: Country | None) -> dict[str, Any] | None:
    return {"id": row.id, "code": row.code, "name": row.name} if row else None


def language_data(row: Language | None) -> dict[str, Any] | None:
    return {"id": row.id, "code": row.code, "name": row.name} if row else None


def content_data(row: Content, *, detailed: bool = True) -> dict[str, Any]:
    localized = localized_fields(
        row.translations,
        {
            "title": row.title,
            "short_description": row.short_description,
            "description": row.description,
            "seo_title": row.seo_title,
            "seo_description": row.seo_description,
        },
    )
    data: dict[str, Any] = {
        "id": row.id,
        "type": row.type,
        "title": localized["title"],
        "slug": row.slug,
        "short_description": localized["short_description"],
        "poster_url": row.poster_url,
        "backdrop_url": row.backdrop_url,
        "release_date": row.release_date,
        "age_rating": row.age_rating,
        "status": row.status,
        "visibility": row.visibility,
        "featured": row.featured,
        "premium": row.premium,
        "rating": row.rating,
        "rating_count": row.rating_count,
        "like_count": row.like_count,
        "published_at": row.published_at,
    }
    if row.type == ContentType.SERIES and row.series:
        data.update(
            series_id=row.series.id,
            total_seasons=row.series.total_seasons,
            total_episodes=row.series.total_episodes,
            series_status=row.series.series_status,
            orientation=row.series.orientation,
        )
    if row.type == ContentType.MOVIE and row.movie:
        data.update(
            movie_id=row.movie.id,
            duration_seconds=row.movie.duration_seconds,
            access_type=row.movie.access_type,
            coin_price=row.movie.coin_price,
        )
    if detailed:
        data.update(
            original_title=row.original_title,
            description=localized["description"],
            trailer_url=row.trailer_url,
            country=country_data(row.country),
            original_language=language_data(row.original_language),
            genres=[{"id": item.id, "name": item.name, "slug": item.slug} for item in row.genres],
            tags=[{"id": item.id, "name": item.name, "slug": item.slug} for item in row.tags],
            cast=[
                {
                    "actor": {
                        "id": credit.actor.id,
                        "name": credit.actor.name,
                        "slug": credit.actor.slug,
                        "photo_url": credit.actor.photo_url,
                    },
                    "character_name": credit.character_name,
                    "role": credit.role,
                    "is_lead": credit.is_lead,
                    "sort_order": credit.sort_order,
                }
                for credit in sorted(row.actor_credits, key=lambda item: item.sort_order)
            ],
            crew=[
                {
                    "member": {
                        "id": credit.crew_member.id,
                        "name": credit.crew_member.name,
                        "slug": credit.crew_member.slug,
                    },
                    "role": credit.role,
                    "sort_order": credit.sort_order,
                }
                for credit in sorted(row.crew_credits, key=lambda item: item.sort_order)
            ],
            license_start=row.license_start,
            license_end=row.license_end,
            allowed_countries=row.allowed_countries,
            blocked_countries=row.blocked_countries,
            seo={
                "title": localized["seo_title"],
                "description": localized["seo_description"],
            },
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
    return data


def video_asset_data(row: VideoAsset | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": row.id,
        "provider": row.provider,
        "provider_asset_id": row.provider_asset_id,
        "status": row.status,
        "duration_seconds": row.duration_seconds,
        "width": row.width,
        "height": row.height,
        "aspect_ratio": row.aspect_ratio,
        "thumbnail_url": row.thumbnail_url,
        "playback_id": row.playback_id,
        "metadata": row.asset_metadata,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def season_data(row: Season) -> dict[str, Any]:
    return {
        "id": row.id,
        "series_id": row.series_id,
        "season_number": row.season_number,
        "title": row.title,
        "description": row.description,
        "poster_url": row.poster_url,
        "release_date": row.release_date,
        "status": row.status,
        "sort_order": row.sort_order,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def episode_data(row: Episode, *, include_asset: bool = True) -> dict[str, Any]:
    localized = localized_fields(
        row.translations,
        {"title": row.title, "description": row.description},
    )
    data: dict[str, Any] = {
        "id": row.id,
        "series_id": row.series_id,
        "season_id": row.season_id,
        "episode_number": row.episode_number,
        "title": localized["title"],
        "description": localized["description"],
        "thumbnail_url": row.thumbnail_url,
        "duration_seconds": row.duration_seconds,
        "orientation": row.orientation,
        "access_type": row.access_type,
        "coin_price": row.coin_price,
        "premium": row.premium,
        "free_from": row.free_from,
        "free_until": row.free_until,
        "published_at": row.published_at,
        "status": row.status,
        "sort_order": row.sort_order,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if include_asset:
        data["video_asset"] = video_asset_data(row.video_asset)
    return data


def subtitle_data(row: Subtitle) -> dict[str, Any]:
    return {
        "id": row.id,
        "video_asset_id": row.video_asset_id,
        "language": language_data(row.language),
        "label": row.label,
        "format": row.format,
        "file_url": row.file_url,
        "is_default": row.is_default,
        "is_auto_generated": row.is_auto_generated,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def snapshot(row: Series | Movie | Episode | Season | VideoAsset | Subtitle) -> dict[str, Any]:
    if isinstance(row, Series):
        return content_data(row.content)
    if isinstance(row, Movie):
        data = content_data(row.content)
        data["video_asset"] = video_asset_data(row.video_asset)
        return data
    if isinstance(row, Episode):
        return episode_data(row)
    if isinstance(row, Season):
        return season_data(row)
    if isinstance(row, VideoAsset):
        return video_asset_data(row) or {}
    return subtitle_data(row)


def apply_model(row: Any, payload: BaseModel, *, exclude: set[str] | None = None) -> None:
    for field, value in payload.model_dump(exclude_unset=True, exclude=exclude or set()).items():
        if field == "metadata" and isinstance(row, VideoAsset):
            row.asset_metadata = value
        else:
            setattr(row, field, value)


def decimal_to_json(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def datetime_to_json(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
