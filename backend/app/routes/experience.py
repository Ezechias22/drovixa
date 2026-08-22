from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy import func, or_, select, update

from app.api.deps import CurrentContext, DbSession, OptionalContext
from app.core.exceptions import AppError
from app.core.rate_limit import rate_limit
from app.models.base import utcnow
from app.models.enums import ContentType, Orientation
from app.models.experience import Notification, NotificationPreference
from app.schemas.common import success
from app.schemas.experience import NotificationPreferenceUpdate, SearchHistoryInput
from app.services.experience import (
    add_favorite,
    clear_searches,
    discover_content,
    favorite_items,
    home_payload,
    notification_data,
    notification_preferences,
    remove_favorite,
    save_search,
    search_content,
    search_suggestions,
    shorts_feed,
    trending_searches,
)

router = APIRouter(tags=["User experience"])
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]
ProfileHeader = Annotated[UUID | None, Header(alias="X-Drovixa-Profile-ID")]


def _meta(page: int, limit: int, total: int) -> dict[str, int]:
    return {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit}


@router.get("/home")
async def home(
    context: OptionalContext, db: DbSession, profile_id: ProfileHeader = None
) -> dict[str, Any]:
    return success(await home_payload(db, context, profile_id))


@router.get("/discover")
async def discover(
    context: OptionalContext,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 20,
    type: ContentType | None = None,
    genre: str | None = Query(default=None, max_length=120),
    country: str | None = Query(default=None, min_length=2, max_length=2),
    language: str | None = Query(default=None, max_length=16),
    release_year: int | None = Query(default=None, ge=1900, le=2100),
    premium: bool | None = None,
    completed: bool | None = None,
    orientation: Orientation | None = None,
    sort: str = Query(default="popular", pattern="^(popular|new|rating)$"),
    profile_id: ProfileHeader = None,
) -> dict[str, Any]:
    rows, total = await discover_content(
        db,
        context=context,
        page=page,
        limit=limit,
        content_type=type,
        genre=genre,
        country=country,
        language=language,
        release_year=release_year,
        premium=premium,
        completed=completed,
        orientation=orientation,
        sort=sort,
        profile_id=profile_id,
    )
    return success(rows, meta=_meta(page, limit, total))


@router.get("/shorts")
async def shorts(
    context: OptionalContext,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 10,
    profile_id: ProfileHeader = None,
) -> dict[str, Any]:
    rows, total = await shorts_feed(
        db, context=context, page=page, limit=limit, profile_id=profile_id
    )
    return success(rows, meta=_meta(page, limit, total))


@router.get("/search", dependencies=[Depends(rate_limit("search", requests=60, window_seconds=60))])
async def search(
    context: OptionalContext,
    db: DbSession,
    q: str = Query(min_length=1, max_length=160),
    page: Page = 1,
    limit: Limit = 20,
    profile_id: ProfileHeader = None,
) -> dict[str, Any]:
    rows, total = await search_content(
        db,
        context=context,
        query=q,
        page=page,
        limit=limit,
        profile_id=profile_id,
    )
    return success(rows, meta=_meta(page, limit, total))


@router.get("/search/suggestions")
async def suggestions(
    context: OptionalContext,
    db: DbSession,
    q: str = Query(default="", max_length=160),
    profile_id: ProfileHeader = None,
) -> dict[str, Any]:
    return success(await search_suggestions(db, context=context, query=q, profile_id=profile_id))


@router.get("/search/trending")
async def search_trending(db: DbSession) -> dict[str, Any]:
    return success(await trending_searches(db))


@router.post("/search/history", status_code=status.HTTP_201_CREATED)
async def add_search_history(
    payload: SearchHistoryInput, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    row = await save_search(db, user_id=context.user.id, query=payload.query)
    return success({"id": row.id, "query": row.query, "updated_at": row.updated_at})


@router.delete("/search/history")
async def delete_search_history(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    return success({"deleted": await clear_searches(db, user_id=context.user.id)})


@router.post("/favorites/{content_id}", status_code=status.HTTP_201_CREATED)
async def create_favorite(
    content_id: UUID, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    row = await add_favorite(db, user_id=context.user.id, content_id=content_id)
    return success({"id": row.id, "content_id": row.content_id, "saved": True})


@router.delete("/favorites/{content_id}")
async def delete_favorite(
    content_id: UUID, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    await remove_favorite(db, user_id=context.user.id, content_id=content_id)
    return success({"content_id": content_id, "saved": False})


@router.get("/favorites")
async def favorites(
    context: CurrentContext, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    rows, total = await favorite_items(db, user_id=context.user.id, page=page, limit=limit)
    return success(rows, meta=_meta(page, limit, total))


@router.get("/notifications")
async def notifications(
    context: CurrentContext,
    db: DbSession,
    page: Page = 1,
    limit: Limit = 20,
    unread_only: bool = False,
) -> dict[str, Any]:
    now = utcnow()
    conditions = [
        Notification.user_id == context.user.id,
        or_(Notification.expires_at.is_(None), Notification.expires_at > now),
    ]
    if unread_only:
        conditions.append(Notification.read_at.is_(None))
    statement = select(Notification).where(*conditions)
    total = int(await db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = list(
        (
            await db.scalars(
                statement.order_by(Notification.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).all()
    )
    unread = int(
        await db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == context.user.id,
                Notification.read_at.is_(None),
                or_(Notification.expires_at.is_(None), Notification.expires_at > now),
            )
        )
        or 0
    )
    return success(
        [notification_data(row) for row in rows],
        meta=dict(_meta(page, limit, total), unread=unread),
    )


@router.patch("/notifications/{notification_id}/read")
async def read_notification(
    notification_id: UUID, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    row = await db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == context.user.id
        )
    )
    if row is None:
        raise AppError("NOT_FOUND", "Notification not found.", status_code=404)
    row.read_at = row.read_at or utcnow()
    await db.commit()
    return success(notification_data(row))


@router.post("/notifications/read-all")
async def read_all_notifications(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == context.user.id, Notification.read_at.is_(None))
        .values(read_at=utcnow())
    )
    await db.commit()
    return success({"updated": int(getattr(result, "rowcount", 0) or 0)})


def _preference_data(row: NotificationPreference) -> dict[str, Any]:
    return {
        "new_episodes": row.new_episodes,
        "promotions": row.promotions,
        "recommendations": row.recommendations,
        "wallet": row.wallet,
        "comments": row.comments,
        "security": True,
    }


@router.get("/notification-preferences")
async def get_notification_preferences(context: CurrentContext, db: DbSession) -> dict[str, Any]:
    return success(_preference_data(await notification_preferences(db, context.user.id)))


@router.patch("/notification-preferences")
async def patch_notification_preferences(
    payload: NotificationPreferenceUpdate, context: CurrentContext, db: DbSession
) -> dict[str, Any]:
    row = await notification_preferences(db, context.user.id)
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(row, key, value)
    row.security = True
    await db.commit()
    return success(_preference_data(row))
