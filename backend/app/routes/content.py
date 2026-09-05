from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import func, or_, select

from app.api.deps import DbSession, OptionalContext
from app.models.base import utcnow
from app.models.catalog import Actor
from app.models.community import Like
from app.models.content import Content, ContentActor, Episode, Series
from app.models.enums import (
    ContentStatus,
    ContentType,
    ContentVisibility,
    EpisodeAccessType,
    LikeTargetType,
)
from app.models.experience import Favorite
from app.models.streaming import UserEntitlement
from app.schemas.common import success
from app.services.catalog import catalog_snapshot
from app.services.content import content_data, episode_data, get_content_by_slug, list_content

router = APIRouter(tags=["Content"])
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]


async def _detail_data(db: DbSession, context: OptionalContext, row: Content) -> dict[str, Any]:
    data = content_data(row)
    data["is_favorite"] = bool(
        context
        and await db.scalar(
            select(Favorite.id).where(
                Favorite.user_id == context.user.id, Favorite.content_id == row.id
            )
        )
    )
    data["is_liked"] = bool(
        context
        and await db.scalar(
            select(Like.id).where(
                Like.user_id == context.user.id,
                Like.target_type == LikeTargetType.CONTENT,
                Like.target_id == row.id,
            )
        )
    )
    return data


def page_meta(page: int, limit: int, total: int) -> dict[str, int]:
    return {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit}


@router.get("/content/{slug}")
async def content_detail(slug: str, context: OptionalContext, db: DbSession) -> dict[str, Any]:
    row = await get_content_by_slug(db, slug, public_only=True)
    return success(await _detail_data(db, context, row))


@router.get("/series")
async def series_list(db: DbSession, page: Page = 1, limit: Limit = 20) -> dict[str, Any]:
    rows, total = await list_content(
        db,
        content_type=ContentType.SERIES,
        page=page,
        limit=limit,
        public_only=True,
    )
    return success(
        [content_data(row, detailed=False) for row in rows],
        meta=page_meta(page, limit, total),
    )


@router.get("/series/{slug}")
async def series_detail(slug: str, context: OptionalContext, db: DbSession) -> dict[str, Any]:
    row = await get_content_by_slug(db, slug, public_only=True)
    if row.type != ContentType.SERIES:
        from app.core.exceptions import AppError

        raise AppError("NOT_FOUND", "The series was not found.", status_code=404)
    data = await _detail_data(db, context, row)
    if row.series:
        data["seasons"] = [
            {
                "id": season.id,
                "season_number": season.season_number,
                "title": season.title,
                "poster_url": season.poster_url,
            }
            for season in sorted(row.series.seasons, key=lambda item: item.sort_order)
            if season.deleted_at is None and season.status == ContentStatus.PUBLISHED
        ]
    return success(data)


@router.get("/series/{series_id}/episodes")
async def series_episodes(
    series_id: UUID,
    context: OptionalContext,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 20,
    season_id: UUID | None = None,
    newest: bool = False,
) -> dict[str, Any]:
    now = utcnow()
    public_series = await db.scalar(
        select(Series)
        .join(Series.content)
        .where(
            Series.id == series_id,
            Content.deleted_at.is_(None),
            Content.status == ContentStatus.PUBLISHED,
            Content.visibility == ContentVisibility.PUBLIC,
            or_(Content.license_start.is_(None), Content.license_start <= now),
            or_(Content.license_end.is_(None), Content.license_end >= now),
        )
    )
    if public_series is None:
        from app.core.exceptions import AppError

        raise AppError("NOT_FOUND", "The series was not found.", status_code=404)
    conditions = [
        Episode.series_id == series_id,
        Episode.deleted_at.is_(None),
        Episode.status == ContentStatus.PUBLISHED,
        or_(Episode.published_at.is_(None), Episode.published_at <= now),
    ]
    if season_id is not None:
        conditions.append(Episode.season_id == season_id)
    statement = select(Episode).where(*conditions)
    total = int(await db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    ordering = Episode.episode_number.desc() if newest else Episode.episode_number.asc()
    rows = (
        await db.scalars(statement.order_by(ordering).offset((page - 1) * limit).limit(limit))
    ).all()
    unlocked_episode_ids: set[UUID] = set()
    if context and rows:
        unlocked_episode_ids = set(
            await db.scalars(
                select(UserEntitlement.episode_id).where(
                    UserEntitlement.user_id == context.user.id,
                    UserEntitlement.episode_id.in_([row.id for row in rows]),
                    UserEntitlement.is_permanent.is_(True),
                )
            )
        )
    data = []
    for row in rows:
        item = episode_data(row, include_asset=False)
        item["unlocked"] = (
            row.access_type == EpisodeAccessType.FREE or row.id in unlocked_episode_ids
        )
        data.append(item)
    return success(data, meta=page_meta(page, limit, total))


@router.get("/movies")
async def movie_list(db: DbSession, page: Page = 1, limit: Limit = 20) -> dict[str, Any]:
    rows, total = await list_content(
        db,
        content_type=ContentType.MOVIE,
        page=page,
        limit=limit,
        public_only=True,
    )
    return success(
        [content_data(row, detailed=False) for row in rows],
        meta=page_meta(page, limit, total),
    )


@router.get("/movies/{slug}")
async def movie_detail(slug: str, context: OptionalContext, db: DbSession) -> dict[str, Any]:
    row = await get_content_by_slug(db, slug, public_only=True)
    if row.type != ContentType.MOVIE:
        from app.core.exceptions import AppError

        raise AppError("NOT_FOUND", "The movie was not found.", status_code=404)
    return success(await _detail_data(db, context, row))


@router.get("/actors/{slug}")
async def actor_detail(slug: str, db: DbSession) -> dict[str, Any]:
    actor = await db.scalar(
        select(Actor).where(Actor.slug == slug, Actor.deleted_at.is_(None), Actor.active.is_(True))
    )
    if actor is None:
        from app.core.exceptions import AppError

        raise AppError("NOT_FOUND", "The actor was not found.", status_code=404)
    now = utcnow()
    rows = (
        await db.scalars(
            select(Content)
            .join(ContentActor, ContentActor.content_id == Content.id)
            .where(
                ContentActor.actor_id == actor.id,
                Content.deleted_at.is_(None),
                Content.status == ContentStatus.PUBLISHED,
                Content.visibility == ContentVisibility.PUBLIC,
                or_(Content.published_at.is_(None), Content.published_at <= now),
            )
            .order_by(Content.release_date.desc())
        )
    ).all()
    data = catalog_snapshot(actor)
    data["content"] = [content_data(row, detailed=False) for row in rows]
    return success(data)
