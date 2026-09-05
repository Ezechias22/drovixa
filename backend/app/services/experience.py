from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import String, case, cast, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import AuthContext
from app.core.exceptions import AppError
from app.models.administration import HomepageSection, HomepageSectionItem
from app.models.base import utcnow
from app.models.catalog import Actor, Country, Genre, Language, Tag
from app.models.content import Content, ContentActor, Episode, Series
from app.models.enums import (
    ContentStatus,
    ContentType,
    ContentVisibility,
    Orientation,
    SeriesStatus,
)
from app.models.experience import Favorite, Notification, NotificationPreference, SearchHistory
from app.services.configuration import public_feature_flags, public_remote_config
from app.services.content import content_data, episode_data
from app.services.monetization import has_active_subscription
from app.services.streaming import continue_watching


def _public_conditions() -> tuple[Any, ...]:
    now = utcnow()
    return (
        Content.deleted_at.is_(None),
        Content.status == ContentStatus.PUBLISHED,
        Content.visibility == ContentVisibility.PUBLIC,
        or_(Content.published_at.is_(None), Content.published_at <= now),
        or_(Content.license_start.is_(None), Content.license_start <= now),
        or_(Content.license_end.is_(None), Content.license_end >= now),
    )


async def _viewer_conditions(
    db: AsyncSession, context: AuthContext | None, profile_id: UUID | None
) -> tuple[Any, ...]:
    conditions = list(_public_conditions())
    if context is not None:
        from app.services.personalization import kids_age_ratings, owned_profile

        profile = await owned_profile(db, context=context, profile_id=profile_id)
        allowed = kids_age_ratings(profile)
        if allowed is not None:
            conditions.append(Content.age_rating.in_(allowed))
    return tuple(conditions)


async def _favorite_ids(db: AsyncSession, user_id: UUID | None) -> set[UUID]:
    if user_id is None:
        return set()
    return set(await db.scalars(select(Favorite.content_id).where(Favorite.user_id == user_id)))


def _cards(
    rows: list[Content], favorites: set[UUID], *, ranked: bool = False
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        item = content_data(row, detailed=False)
        item["is_favorite"] = row.id in favorites
        if ranked:
            item["rank"] = index + 1
        result.append(item)
    return result


async def home_payload(
    db: AsyncSession, context: AuthContext | None, profile_id: UUID | None = None
) -> dict[str, Any]:
    conditions = await _viewer_conditions(db, context, profile_id)
    user_id = context.user.id if context else None
    favorites = await _favorite_ids(db, user_id)

    async def rows(
        ordering: tuple[Any, ...], *, premium: bool | None = None, limit: int = 20
    ) -> list[Content]:
        statement = select(Content).where(*conditions)
        if premium is not None:
            statement = statement.where(Content.premium.is_(premium))
        return list((await db.scalars(statement.order_by(*ordering).limit(limit))).all())

    hero = list(
        (
            await db.scalars(
                select(Content)
                .where(*conditions, Content.featured.is_(True))
                .order_by(Content.published_at.desc())
                .limit(5)
            )
        ).all()
    )
    if not hero:
        hero = await rows((Content.published_at.desc(), Content.created_at.desc()), limit=5)
    trending = await rows((Content.view_count.desc(), Content.like_count.desc()))
    latest = await rows((Content.published_at.desc(), Content.created_at.desc()))
    premium = await rows((Content.published_at.desc(),), premium=True)
    top = await rows((Content.view_count.desc(), Content.rating.desc()), limit=10)

    configured_sections = list(
        (
            await db.scalars(
                select(HomepageSection)
                .where(
                    HomepageSection.active.is_(True),
                    or_(HomepageSection.starts_at.is_(None), HomepageSection.starts_at <= utcnow()),
                    or_(HomepageSection.ends_at.is_(None), HomepageSection.ends_at >= utcnow()),
                )
                .options(
                    selectinload(HomepageSection.items).selectinload(HomepageSectionItem.content)
                )
                .order_by(HomepageSection.sort_order, HomepageSection.created_at)
            )
        )
        .unique()
        .all()
    )
    if configured_sections:
        premium_user = bool(user_id and await has_active_subscription(db, user_id=user_id))
        dynamic_sections: list[dict[str, Any]] = []
        progress_cache: list[dict[str, Any]] | None = None
        for section in configured_sections:
            if section.target_subscription == "premium" and not premium_user:
                continue
            if section.target_subscription == "non_premium" and premium_user:
                continue
            if section.target_countries and (
                context is None or context.user.country_code not in section.target_countries
            ):
                continue
            if section.target_languages and (
                context is None or context.user.language_code not in section.target_languages
            ):
                continue
            if section.algorithm == "continue_watching":
                if user_id is None:
                    continue
                if progress_cache is None:
                    progress_cache, _ = await continue_watching(
                        db, user_id=user_id, page=1, limit=section.max_items
                    )
                dynamic_items: list[dict[str, Any]] = progress_cache
            else:
                statement = select(Content).where(*conditions)
                if section.algorithm == "manual":
                    manual_content = list(
                        (
                            await db.scalars(
                                select(Content)
                                .join(
                                    HomepageSectionItem,
                                    HomepageSectionItem.content_id == Content.id,
                                )
                                .where(
                                    *conditions,
                                    HomepageSectionItem.section_id == section.id,
                                )
                                .order_by(HomepageSectionItem.sort_order)
                                .limit(section.max_items)
                            )
                        ).all()
                    )
                    if not manual_content and section.key == "premium_originals":
                        manual_content = premium[: section.max_items]
                    section_rows = manual_content
                else:
                    if section.algorithm == "genre" and section.genre_id:
                        statement = statement.where(
                            Content.genres.any(Genre.id == section.genre_id)
                        )
                    ordering = {
                        "latest": (Content.published_at.desc(), Content.created_at.desc()),
                        "recently_added": (Content.created_at.desc(),),
                        "top_10": (Content.view_count.desc(), Content.rating.desc()),
                        "recommended": (Content.rating.desc(), Content.view_count.desc()),
                        "most_watched": (Content.view_count.desc(),),
                        "trending": (Content.view_count.desc(), Content.like_count.desc()),
                        "genre": (Content.view_count.desc(), Content.rating.desc()),
                    }.get(
                        section.algorithm,
                        (Content.view_count.desc(), Content.published_at.desc()),
                    )
                    section_rows = list(
                        (
                            await db.scalars(statement.order_by(*ordering).limit(section.max_items))
                        ).all()
                    )
                dynamic_items = _cards(
                    section_rows,
                    favorites,
                    ranked=section.algorithm == "top_10",
                )
            if dynamic_items:
                dynamic_sections.append(
                    {
                        "id": section.key,
                        "title": section.title,
                        "algorithm": section.algorithm,
                        "presentation": section.presentation,
                        "items": dynamic_items,
                    }
                )
        return {
            "hero": _cards(hero, favorites),
            "sections": dynamic_sections,
            "feature_flags": await public_feature_flags(db),
            "remote_config": await public_remote_config(db),
        }

    sections: list[dict[str, Any]] = []
    if user_id:
        progress, _ = await continue_watching(db, user_id=user_id, page=1, limit=20)
        if progress:
            sections.append(
                {
                    "id": "continue_watching",
                    "title": "Continue Watching",
                    "algorithm": "continue_watching",
                    "presentation": "progress",
                    "items": progress,
                }
            )
    for key, title, algorithm, default_rows, presentation in (
        ("trending", "Trending Now", "trending", trending, "poster"),
        ("top_10", "Top 10 Today", "top_10", top, "ranked"),
        ("new_releases", "New Releases", "latest", latest, "poster"),
        ("premium_originals", "Premium Originals", "manual", premium, "wide"),
    ):
        if default_rows:
            sections.append(
                {
                    "id": key,
                    "title": title,
                    "algorithm": algorithm,
                    "presentation": presentation,
                    "items": _cards(default_rows, favorites, ranked=key == "top_10"),
                }
            )
    return {
        "hero": _cards(hero, favorites),
        "sections": sections,
        "feature_flags": await public_feature_flags(db),
        "remote_config": await public_remote_config(db),
    }


async def discover_content(
    db: AsyncSession,
    *,
    context: AuthContext | None,
    page: int,
    limit: int,
    content_type: ContentType | None,
    genre: str | None,
    country: str | None,
    language: str | None,
    release_year: int | None,
    premium: bool | None,
    completed: bool | None,
    orientation: Orientation | None,
    sort: str,
    profile_id: UUID | None = None,
) -> tuple[list[dict[str, Any]], int]:
    statement = select(Content).where(*(await _viewer_conditions(db, context, profile_id)))
    if content_type:
        statement = statement.where(Content.type == content_type)
    if genre:
        statement = statement.where(Content.genres.any(Genre.slug == genre.casefold()))
    if country:
        statement = statement.where(Content.country.has(Country.code == country.upper()))
    if language:
        statement = statement.where(Content.original_language.has(Language.code == language))
    if release_year:
        statement = statement.where(
            Content.release_date >= date(release_year, 1, 1),
            Content.release_date <= date(release_year, 12, 31),
        )
    if premium is not None:
        statement = statement.where(Content.premium.is_(premium))
    if completed is not None:
        statement = statement.where(
            Content.series.has(
                Series.series_status
                == (SeriesStatus.COMPLETED if completed else SeriesStatus.ONGOING)
            )
        )
    if orientation is not None:
        statement = statement.where(Content.series.has(Series.orientation == orientation))
    total = int(await db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    ordering: tuple[Any, ...] = {
        "popular": (Content.view_count.desc(), Content.rating.desc()),
        "rating": (Content.rating.desc(), Content.view_count.desc()),
        "new": (Content.published_at.desc(), Content.created_at.desc()),
    }.get(sort, (Content.view_count.desc(), Content.published_at.desc()))
    rows = list(
        (
            await db.scalars(statement.order_by(*ordering).offset((page - 1) * limit).limit(limit))
        ).all()
    )
    return _cards(rows, await _favorite_ids(db, context.user.id if context else None)), total


async def search_content(
    db: AsyncSession,
    *,
    context: AuthContext | None,
    query: str,
    page: int,
    limit: int,
    profile_id: UUID | None = None,
) -> tuple[list[dict[str, Any]], int]:
    q = " ".join(query.split()).casefold()
    if not q:
        return [], 0
    pattern = f"%{q}%"
    searchable = or_(
        func.lower(Content.title).like(pattern),
        func.lower(func.coalesce(Content.original_title, "")).like(pattern),
        func.lower(func.coalesce(Content.short_description, "")).like(pattern),
        func.lower(func.coalesce(Content.description, "")).like(pattern),
        func.lower(cast(Content.translations, String)).like(pattern),
        Content.genres.any(func.lower(Genre.name).like(pattern)),
        Content.tags.any(func.lower(Tag.name).like(pattern)),
        Content.actor_credits.any(ContentActor.actor.has(func.lower(Actor.name).like(pattern))),
        Content.country.has(func.lower(Country.name).like(pattern)),
        Content.original_language.has(func.lower(Language.name).like(pattern)),
    )
    statement = select(Content).where(
        *(await _viewer_conditions(db, context, profile_id)), searchable
    )
    total = int(await db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    exact = case((func.lower(Content.title) == q, 0), else_=1)
    rows = list(
        (
            await db.scalars(
                statement.order_by(exact, Content.featured.desc(), Content.view_count.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).all()
    )
    return _cards(rows, await _favorite_ids(db, context.user.id if context else None)), total


async def search_suggestions(
    db: AsyncSession,
    *,
    context: AuthContext | None,
    query: str,
    profile_id: UUID | None = None,
) -> dict[str, Any]:
    q = " ".join(query.split()).casefold()
    recent: list[str] = []
    if context:
        recent = list(
            await db.scalars(
                select(SearchHistory.query)
                .where(SearchHistory.user_id == context.user.id)
                .order_by(SearchHistory.updated_at.desc())
                .limit(8)
            )
        )
    if not q:
        return {
            "recent": recent,
            "popular": await trending_searches(db),
            "content": [],
            "actors": [],
            "genres": [],
        }
    pattern = f"%{q}%"
    content = list(
        (
            await db.scalars(
                select(Content)
                .where(
                    *(await _viewer_conditions(db, context, profile_id)),
                    or_(
                        func.lower(Content.title).like(pattern),
                        func.lower(cast(Content.translations, String)).like(pattern),
                    ),
                )
                .order_by(Content.view_count.desc())
                .limit(6)
            )
        ).all()
    )
    actors = list(
        (
            await db.scalars(
                select(Actor)
                .where(
                    Actor.deleted_at.is_(None),
                    Actor.active.is_(True),
                    func.lower(Actor.name).like(pattern),
                )
                .limit(5)
            )
        ).all()
    )
    genres = list(
        (
            await db.scalars(
                select(Genre)
                .where(Genre.active.is_(True), func.lower(Genre.name).like(pattern))
                .limit(5)
            )
        ).all()
    )
    return {
        "recent": recent,
        "popular": await trending_searches(db),
        "content": _cards(content, await _favorite_ids(db, context.user.id if context else None)),
        "actors": [
            {"id": row.id, "name": row.name, "slug": row.slug, "photo_url": row.photo_url}
            for row in actors
        ],
        "genres": [{"id": row.id, "name": row.name, "slug": row.slug} for row in genres],
    }


async def trending_searches(db: AsyncSession) -> list[str]:
    rows = (
        await db.execute(
            select(SearchHistory.query, func.count(SearchHistory.id).label("searches"))
            .group_by(SearchHistory.query)
            .order_by(
                func.count(SearchHistory.id).desc(), func.max(SearchHistory.updated_at).desc()
            )
            .limit(10)
        )
    ).all()
    return [row.query for row in rows]


async def shorts_feed(
    db: AsyncSession,
    *,
    context: AuthContext | None,
    page: int,
    limit: int,
    profile_id: UUID | None = None,
) -> tuple[list[dict[str, Any]], int]:
    now = utcnow()
    conditions = (
        Episode.deleted_at.is_(None),
        Episode.status == ContentStatus.PUBLISHED,
        or_(Episode.published_at.is_(None), Episode.published_at <= now),
        Episode.orientation == Orientation.VERTICAL,
        *(await _viewer_conditions(db, context, profile_id)),
    )
    statement = select(Episode).join(Episode.series).join(Series.content).where(*conditions)
    total = int(await db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = list(
        (
            await db.scalars(
                statement.options(selectinload(Episode.series).selectinload(Series.content))
                .order_by(Episode.published_at.desc(), Episode.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).all()
    )
    favorites = await _favorite_ids(db, context.user.id if context else None)
    result = []
    for row in rows:
        item = episode_data(row, include_asset=False)
        series = content_data(row.series.content, detailed=False)
        series["is_favorite"] = row.series.content.id in favorites
        item["series"] = series
        result.append(item)
    return result, total


async def save_search(db: AsyncSession, *, user_id: UUID, query: str) -> SearchHistory:
    normalized = " ".join(query.split()).casefold()
    row = await db.scalar(
        select(SearchHistory).where(
            SearchHistory.user_id == user_id, SearchHistory.normalized_query == normalized
        )
    )
    if row:
        row.query = " ".join(query.split())
        row.updated_at = utcnow()
    else:
        row = SearchHistory(
            user_id=user_id, query=" ".join(query.split()), normalized_query=normalized
        )
        db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def clear_searches(db: AsyncSession, *, user_id: UUID) -> int:
    result = await db.execute(delete(SearchHistory).where(SearchHistory.user_id == user_id))
    await db.commit()
    return int(getattr(result, "rowcount", 0) or 0)


async def add_favorite(db: AsyncSession, *, user_id: UUID, content_id: UUID) -> Favorite:
    content = await db.scalar(
        select(Content).where(Content.id == content_id, *_public_conditions())
    )
    if content is None:
        raise AppError("NOT_FOUND", "Content not found.", status_code=404)
    existing = await db.scalar(
        select(Favorite).where(Favorite.user_id == user_id, Favorite.content_id == content_id)
    )
    if existing:
        return existing
    row = Favorite(user_id=user_id, content_id=content_id)
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        recovered = await db.scalar(
            select(Favorite).where(Favorite.user_id == user_id, Favorite.content_id == content_id)
        )
        if recovered is None:
            raise
        row = recovered
    return row


async def remove_favorite(db: AsyncSession, *, user_id: UUID, content_id: UUID) -> None:
    await db.execute(
        delete(Favorite).where(Favorite.user_id == user_id, Favorite.content_id == content_id)
    )
    await db.commit()


async def favorite_items(
    db: AsyncSession, *, user_id: UUID, page: int, limit: int
) -> tuple[list[dict[str, Any]], int]:
    statement = (
        select(Favorite).where(Favorite.user_id == user_id).options(selectinload(Favorite.content))
    )
    total = int(await db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = list(
        (
            await db.scalars(
                statement.order_by(Favorite.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).all()
    )
    return _cards([row.content for row in rows], {row.content_id for row in rows}), total


def notification_data(row: Notification) -> dict[str, Any]:
    return {
        "id": row.id,
        "type": row.type,
        "title": row.title,
        "body": row.body,
        "image_url": row.image_url,
        "action_url": row.action_url,
        "payload": row.payload,
        "read": row.read_at is not None,
        "created_at": row.created_at,
    }


async def notification_preferences(db: AsyncSession, user_id: UUID) -> NotificationPreference:
    row = await db.get(NotificationPreference, user_id)
    if row is None:
        row = NotificationPreference(user_id=user_id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row
