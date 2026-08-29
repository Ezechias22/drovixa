from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Header, Query, Request, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import ColumnElement, func, select, update

from app.api.deps import DbSession, require_permission
from app.core.exceptions import AppError
from app.models.base import utcnow
from app.models.catalog import Language
from app.models.content import Content, ContentMedia, Episode, Movie, Season, Subtitle, VideoAsset
from app.models.enums import ContentStatus, ContentType, EpisodeAccessType, VideoStatus
from app.models.user import User
from app.schemas.common import success
from app.schemas.content import (
    EpisodeCreate,
    EpisodeUpdate,
    MovieCreate,
    MovieUpdate,
    SeasonCreate,
    SeasonUpdate,
    SeriesCreate,
    SeriesUpdate,
    SubtitleCreate,
    SubtitleUpdate,
    VideoAssetCreate,
    VideoAssetUpdate,
)
from app.services.audit import add_audit_log
from app.services.catalog import require_reference
from app.services.content import (
    apply_model,
    archive_content,
    content_data,
    create_movie,
    create_series,
    episode_data,
    get_entity,
    get_movie,
    get_series,
    list_content,
    publish_content,
    publish_episode,
    publish_season,
    refresh_series_totals,
    season_data,
    snapshot,
    subtitle_data,
    update_movie,
    update_series,
    validate_episode_links,
    video_asset_data,
)

router = APIRouter(prefix="/admin", tags=["Admin content"])
Viewer = Annotated[User, require_permission("content.view")]
Creator = Annotated[User, require_permission("content.create")]
Editor = Annotated[User, require_permission("content.edit")]
Deleter = Annotated[User, require_permission("content.delete")]
Publisher = Annotated[User, require_permission("content.publish")]
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]


def _meta(page: int, limit: int, total: int) -> dict[str, int]:
    return {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit}


def _image_mime_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def _audit_commit(
    db: DbSession,
    *,
    request: Request,
    admin: User,
    action: str,
    entity_type: str,
    entity_id: UUID,
    old: dict[str, Any] | None,
    new: dict[str, Any] | None,
) -> None:
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        old_value=jsonable_encoder(old) if old is not None else None,
        new_value=jsonable_encoder(new) if new is not None else None,
    )
    await db.commit()


@router.post("/content/{content_id}/media", status_code=status.HTTP_201_CREATED)
async def upload_content_media(
    content_id: UUID,
    request: Request,
    admin: Editor,
    db: DbSession,
    image_data: Annotated[bytes, Body()],
    variant: Annotated[str, Query(pattern="^(poster|backdrop|thumbnail)$")] = "poster",
    public_api_origin: Annotated[
        str | None, Header(alias="X-Public-API-Origin", max_length=500)
    ] = None,
) -> dict[str, Any]:
    if not image_data or len(image_data) > 1_800_000:
        raise AppError(
            "INVALID_IMAGE_SIZE",
            "Cover images must be between 1 byte and 1.8 MB.",
            status_code=413,
        )
    mime_type = _image_mime_type(image_data)
    if mime_type is None:
        raise AppError(
            "INVALID_IMAGE_TYPE",
            "Use a JPG, PNG or WebP cover image.",
            status_code=422,
        )
    content = await db.scalar(
        select(Content).where(Content.id == content_id, Content.deleted_at.is_(None))
    )
    if content is None:
        raise AppError("NOT_FOUND", "Content not found.", status_code=404)
    row = ContentMedia(
        content_id=content.id,
        created_by_id=admin.id,
        variant=variant,
        mime_type=mime_type,
        byte_size=len(image_data),
        image_data=image_data,
    )
    db.add(row)
    await db.flush()
    origin = (public_api_origin or str(request.base_url)).rstrip("/")
    api_prefix = request.url.path.split("/admin/", 1)[0]
    media_url = f"{origin}{api_prefix}/media/content/{row.id}"
    if variant == "poster":
        content.poster_url = media_url
    elif variant == "backdrop":
        content.backdrop_url = media_url
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="content.media_upload",
        entity_type="content",
        entity_id=str(content.id),
        old_value=None,
        new_value={
            "media_id": str(row.id),
            "variant": variant,
            "mime_type": mime_type,
            "byte_size": len(image_data),
            "url": media_url,
        },
    )
    await db.commit()
    return success({"id": row.id, "variant": variant, "url": media_url})


@router.post("/content/{content_id}/subtitle-file", status_code=status.HTTP_201_CREATED)
async def upload_subtitle_file(
    content_id: UUID,
    request: Request,
    admin: Editor,
    db: DbSession,
    subtitle_data: Annotated[bytes, Body()],
    subtitle_format: Annotated[str, Query(alias="format", pattern="^(vtt|srt)$")],
    public_api_origin: Annotated[
        str | None, Header(alias="X-Public-API-Origin", max_length=500)
    ] = None,
) -> dict[str, Any]:
    if not subtitle_data or len(subtitle_data) > 512_000:
        raise AppError(
            "INVALID_SUBTITLE_SIZE",
            "Subtitle files must be between 1 byte and 500 KB.",
            status_code=413,
        )
    try:
        text = subtitle_data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppError(
            "INVALID_SUBTITLE_FILE",
            "Use a UTF-8 WebVTT or SRT subtitle file.",
            status_code=422,
        ) from exc
    if "-->" not in text:
        raise AppError(
            "INVALID_SUBTITLE_FILE",
            "The selected file does not contain valid subtitle timestamps.",
            status_code=422,
        )
    content = await db.scalar(
        select(Content).where(Content.id == content_id, Content.deleted_at.is_(None))
    )
    if content is None:
        raise AppError("NOT_FOUND", "Content not found.", status_code=404)
    normalized = text.replace("\r\n", "\n").encode("utf-8")
    mime_type = (
        "text/vtt; charset=utf-8"
        if subtitle_format == "vtt"
        else "application/x-subrip; charset=utf-8"
    )
    row = ContentMedia(
        content_id=content.id,
        created_by_id=admin.id,
        variant="subtitle",
        mime_type=mime_type,
        byte_size=len(normalized),
        image_data=normalized,
    )
    db.add(row)
    await db.flush()
    origin = (public_api_origin or str(request.base_url)).rstrip("/")
    api_prefix = request.url.path.split("/admin/", 1)[0]
    media_url = f"{origin}{api_prefix}/media/content/{row.id}"
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action="subtitle.file_upload",
        entity_type="content",
        entity_id=str(content.id),
        old_value=None,
        new_value={"media_id": str(row.id), "format": subtitle_format, "url": media_url},
    )
    await db.commit()
    return success({"id": row.id, "variant": "subtitle", "url": media_url})


@router.get("/series")
async def admin_series(
    _: Viewer, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    rows, total = await list_content(
        db, content_type=ContentType.SERIES, page=page, limit=limit, public_only=False
    )
    return success(
        [content_data(row, detailed=False) for row in rows], meta=_meta(page, limit, total)
    )


@router.post("/series", status_code=status.HTTP_201_CREATED)
async def admin_create_series(
    payload: SeriesCreate, request: Request, admin: Creator, db: DbSession
) -> dict[str, Any]:
    row = await create_series(db, payload)
    new = snapshot(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="series.create",
        entity_type="series",
        entity_id=row.id,
        old=None,
        new=new,
    )
    return success(new)


@router.get("/series/{series_id}")
async def admin_series_detail(series_id: UUID, _: Viewer, db: DbSession) -> dict[str, Any]:
    return success(snapshot(await get_series(db, series_id)))


@router.patch("/series/{series_id}")
async def admin_update_series(
    series_id: UUID, payload: SeriesUpdate, request: Request, admin: Editor, db: DbSession
) -> dict[str, Any]:
    row = await get_series(db, series_id)
    old = snapshot(row)
    await update_series(db, row, payload)
    new = snapshot(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="series.update",
        entity_type="series",
        entity_id=row.id,
        old=old,
        new=new,
    )
    return success(new)


@router.post("/series/{series_id}/publish")
async def admin_publish_series(
    series_id: UUID, request: Request, admin: Publisher, db: DbSession
) -> dict[str, Any]:
    row = await get_series(db, series_id)
    old = snapshot(row)
    await publish_content(db, row)
    new = snapshot(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="series.publish",
        entity_type="series",
        entity_id=row.id,
        old=old,
        new=new,
    )
    return success(new)


@router.delete("/series/{series_id}")
async def admin_archive_series(
    series_id: UUID, request: Request, admin: Deleter, db: DbSession
) -> dict[str, Any]:
    row = await get_series(db, series_id)
    old = snapshot(row)
    await archive_content(db, row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="series.archive",
        entity_type="series",
        entity_id=row.id,
        old=old,
        new={"archived": True},
    )
    return success({"id": row.id, "archived": True})


@router.get("/movies")
async def admin_movies(
    _: Viewer, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    rows, total = await list_content(
        db, content_type=ContentType.MOVIE, page=page, limit=limit, public_only=False
    )
    return success(
        [content_data(row, detailed=False) for row in rows], meta=_meta(page, limit, total)
    )


@router.post("/movies", status_code=status.HTTP_201_CREATED)
async def admin_create_movie(
    payload: MovieCreate, request: Request, admin: Creator, db: DbSession
) -> dict[str, Any]:
    row = await create_movie(db, payload)
    new = snapshot(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="movie.create",
        entity_type="movie",
        entity_id=row.id,
        old=None,
        new=new,
    )
    return success(new)


@router.get("/movies/{movie_id}")
async def admin_movie_detail(movie_id: UUID, _: Viewer, db: DbSession) -> dict[str, Any]:
    return success(snapshot(await get_movie(db, movie_id)))


@router.patch("/movies/{movie_id}")
async def admin_update_movie(
    movie_id: UUID, payload: MovieUpdate, request: Request, admin: Editor, db: DbSession
) -> dict[str, Any]:
    row = await get_movie(db, movie_id)
    old = snapshot(row)
    await update_movie(db, row, payload)
    new = snapshot(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="movie.update",
        entity_type="movie",
        entity_id=row.id,
        old=old,
        new=new,
    )
    return success(new)


@router.post("/movies/{movie_id}/publish")
async def admin_publish_movie(
    movie_id: UUID, request: Request, admin: Publisher, db: DbSession
) -> dict[str, Any]:
    row = await get_movie(db, movie_id)
    old = snapshot(row)
    await publish_content(db, row)
    new = snapshot(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="movie.publish",
        entity_type="movie",
        entity_id=row.id,
        old=old,
        new=new,
    )
    return success(new)


@router.delete("/movies/{movie_id}")
async def admin_archive_movie(
    movie_id: UUID, request: Request, admin: Deleter, db: DbSession
) -> dict[str, Any]:
    row = await get_movie(db, movie_id)
    old = snapshot(row)
    await archive_content(db, row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="movie.archive",
        entity_type="movie",
        entity_id=row.id,
        old=old,
        new={"archived": True},
    )
    return success({"id": row.id, "archived": True})


@router.get("/seasons")
async def admin_seasons(
    _: Viewer, db: DbSession, series_id: UUID, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    await get_series(db, series_id)
    statement = select(Season).where(Season.series_id == series_id, Season.deleted_at.is_(None))
    total = int(await db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = (
        await db.scalars(
            statement.order_by(Season.sort_order, Season.season_number)
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()
    return success([season_data(row) for row in rows], meta=_meta(page, limit, total))


@router.post("/seasons", status_code=status.HTTP_201_CREATED)
async def admin_create_season(
    payload: SeasonCreate, request: Request, admin: Creator, db: DbSession
) -> dict[str, Any]:
    series = await get_series(db, payload.series_id)
    values = payload.model_dump()
    values["status"] = ContentStatus.DRAFT
    row = Season(**values, series=series)
    db.add(row)
    await db.flush()
    await refresh_series_totals(db, series)
    new = season_data(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="season.create",
        entity_type="season",
        entity_id=row.id,
        old=None,
        new=new,
    )
    return success(new)


@router.patch("/seasons/{season_id}")
async def admin_update_season(
    season_id: UUID, payload: SeasonUpdate, request: Request, admin: Editor, db: DbSession
) -> dict[str, Any]:
    row = await get_entity(db, Season, season_id, label="season")
    old = season_data(row)
    apply_model(row, payload)
    await db.flush()
    new = season_data(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="season.update",
        entity_type="season",
        entity_id=row.id,
        old=old,
        new=new,
    )
    return success(new)


@router.post("/seasons/{season_id}/publish")
async def admin_publish_season(
    season_id: UUID, request: Request, admin: Publisher, db: DbSession
) -> dict[str, Any]:
    row = await get_entity(db, Season, season_id, label="season")
    old = season_data(row)
    await publish_season(db, row)
    new = season_data(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="season.publish",
        entity_type="season",
        entity_id=row.id,
        old=old,
        new=new,
    )
    return success(new)


@router.delete("/seasons/{season_id}")
async def admin_delete_season(
    season_id: UUID, request: Request, admin: Deleter, db: DbSession
) -> dict[str, Any]:
    row = await get_entity(db, Season, season_id, label="season")
    if (
        await db.scalar(
            select(Episode.id).where(Episode.season_id == row.id, Episode.deleted_at.is_(None))
        )
        is not None
    ):
        raise AppError("CONFLICT", "Move or archive the season episodes first.", status_code=409)
    old = season_data(row)
    row.deleted_at = utcnow()
    series = await get_series(db, row.series_id)
    await refresh_series_totals(db, series)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="season.archive",
        entity_type="season",
        entity_id=row.id,
        old=old,
        new={"archived": True},
    )
    return success({"id": row.id, "archived": True})


@router.get("/episodes")
async def admin_episodes(
    _: Viewer, db: DbSession, series_id: UUID, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    await get_series(db, series_id)
    statement = select(Episode).where(Episode.series_id == series_id, Episode.deleted_at.is_(None))
    total = int(await db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = (
        await db.scalars(
            statement.order_by(Episode.sort_order, Episode.episode_number)
            .offset((page - 1) * limit)
            .limit(limit)
        )
    ).all()
    return success([episode_data(row) for row in rows], meta=_meta(page, limit, total))


@router.post("/episodes", status_code=status.HTTP_201_CREATED)
async def admin_create_episode(
    payload: EpisodeCreate, request: Request, admin: Creator, db: DbSession
) -> dict[str, Any]:
    await validate_episode_links(
        db,
        series_id=payload.series_id,
        season_id=payload.season_id,
        video_asset_id=payload.video_asset_id,
    )
    values = payload.model_dump()
    row = Episode(**values)
    if payload.video_asset_id:
        row.video_asset = await get_entity(
            db, VideoAsset, payload.video_asset_id, label="video asset"
        )
    db.add(row)
    await db.flush()
    series = await get_series(db, payload.series_id)
    await refresh_series_totals(db, series)
    new = episode_data(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="episode.create",
        entity_type="episode",
        entity_id=row.id,
        old=None,
        new=new,
    )
    return success(new)


@router.get("/episodes/{episode_id}")
async def admin_episode_detail(episode_id: UUID, _: Viewer, db: DbSession) -> dict[str, Any]:
    return success(episode_data(await get_entity(db, Episode, episode_id, label="episode")))


def _validate_episode_update(row: Episode, changes: dict[str, Any]) -> None:
    start = changes.get("free_from", row.free_from)
    end = changes.get("free_until", row.free_until)
    access = changes.get("access_type", row.access_type)
    price = changes.get("coin_price", row.coin_price)
    if start and end and end < start:
        raise AppError("VALIDATION_ERROR", "free_until must follow free_from.", status_code=422)
    if access in {EpisodeAccessType.COIN_UNLOCK, EpisodeAccessType.PREMIUM_OR_COIN} and price < 1:
        raise AppError(
            "VALIDATION_ERROR", "coin_price must be positive for coin access.", status_code=422
        )


@router.patch("/episodes/{episode_id}")
async def admin_update_episode(
    episode_id: UUID, payload: EpisodeUpdate, request: Request, admin: Editor, db: DbSession
) -> dict[str, Any]:
    row = await get_entity(db, Episode, episode_id, label="episode")
    old = episode_data(row)
    changes = payload.model_dump(exclude_unset=True)
    _validate_episode_update(row, changes)
    await validate_episode_links(
        db,
        series_id=row.series_id,
        season_id=changes.get("season_id", row.season_id),
        video_asset_id=changes.get("video_asset_id", row.video_asset_id),
    )
    apply_model(row, payload)
    if "video_asset_id" in changes:
        row.video_asset = (
            await get_entity(db, VideoAsset, changes["video_asset_id"], label="video asset")
            if changes["video_asset_id"]
            else None
        )
    await db.flush()
    new = episode_data(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="episode.update",
        entity_type="episode",
        entity_id=row.id,
        old=old,
        new=new,
    )
    return success(new)


@router.post("/episodes/{episode_id}/publish")
async def admin_publish_episode(
    episode_id: UUID, request: Request, admin: Publisher, db: DbSession
) -> dict[str, Any]:
    row = await get_entity(db, Episode, episode_id, label="episode")
    old = episode_data(row)
    await publish_episode(db, row)
    new = episode_data(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="episode.publish",
        entity_type="episode",
        entity_id=row.id,
        old=old,
        new=new,
    )
    return success(new)


@router.delete("/episodes/{episode_id}")
async def admin_delete_episode(
    episode_id: UUID, request: Request, admin: Deleter, db: DbSession
) -> dict[str, Any]:
    row = await get_entity(db, Episode, episode_id, label="episode")
    old = episode_data(row)
    row.deleted_at = utcnow()
    row.status = ContentStatus.ARCHIVED
    series = await get_series(db, row.series_id)
    await refresh_series_totals(db, series)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="episode.archive",
        entity_type="episode",
        entity_id=row.id,
        old=old,
        new={"archived": True},
    )
    return success({"id": row.id, "archived": True})


@router.get("/video-assets")
async def admin_video_assets(
    _: Viewer, db: DbSession, page: Page = 1, limit: Limit = 20, state: VideoStatus | None = None
) -> dict[str, Any]:
    conditions: list[ColumnElement[bool]] = [VideoAsset.deleted_at.is_(None)]
    if state:
        conditions.append(VideoAsset.status == state)
    statement = select(VideoAsset).where(*conditions)
    total = int(await db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = (
        await db.scalars(
            statement.order_by(VideoAsset.created_at.desc()).offset((page - 1) * limit).limit(limit)
        )
    ).all()
    return success([video_asset_data(row) for row in rows], meta=_meta(page, limit, total))


@router.post("/video-assets", status_code=status.HTTP_201_CREATED)
async def admin_create_video_asset(
    payload: VideoAssetCreate, request: Request, admin: Creator, db: DbSession
) -> dict[str, Any]:
    values = payload.model_dump()
    values["asset_metadata"] = values.pop("metadata")
    row = VideoAsset(**values)
    db.add(row)
    await db.flush()
    new = video_asset_data(row) or {}
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="video_asset.create",
        entity_type="video_asset",
        entity_id=row.id,
        old=None,
        new=new,
    )
    return success(new)


@router.patch("/video-assets/{asset_id}")
async def admin_update_video_asset(
    asset_id: UUID, payload: VideoAssetUpdate, request: Request, admin: Editor, db: DbSession
) -> dict[str, Any]:
    row = await get_entity(db, VideoAsset, asset_id, label="video asset")
    old = video_asset_data(row) or {}
    apply_model(row, payload)
    await db.flush()
    new = video_asset_data(row) or {}
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="video_asset.update",
        entity_type="video_asset",
        entity_id=row.id,
        old=old,
        new=new,
    )
    return success(new)


@router.delete("/video-assets/{asset_id}")
async def admin_delete_video_asset(
    asset_id: UUID, request: Request, admin: Deleter, db: DbSession
) -> dict[str, Any]:
    row = await get_entity(db, VideoAsset, asset_id, label="video asset")
    used = await db.scalar(
        select(Episode.id).where(Episode.video_asset_id == row.id, Episode.deleted_at.is_(None))
    )
    used = used or await db.scalar(select(Movie.id).where(Movie.video_asset_id == row.id))
    if used:
        raise AppError("CONFLICT", "The video asset is still attached to content.", status_code=409)
    old = video_asset_data(row) or {}
    row.status = VideoStatus.DELETED
    row.deleted_at = utcnow()
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="video_asset.archive",
        entity_type="video_asset",
        entity_id=row.id,
        old=old,
        new={"archived": True},
    )
    return success({"id": row.id, "archived": True})


@router.get("/subtitles")
async def admin_subtitles(
    _: Viewer, db: DbSession, video_asset_id: UUID, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    await get_entity(db, VideoAsset, video_asset_id, label="video asset")
    statement = select(Subtitle).where(
        Subtitle.video_asset_id == video_asset_id, Subtitle.deleted_at.is_(None)
    )
    total = int(await db.scalar(select(func.count()).select_from(statement.subquery())) or 0)
    rows = (
        await db.scalars(statement.order_by(Subtitle.label).offset((page - 1) * limit).limit(limit))
    ).all()
    return success([subtitle_data(row) for row in rows], meta=_meta(page, limit, total))


@router.post("/subtitles", status_code=status.HTTP_201_CREATED)
async def admin_create_subtitle(
    payload: SubtitleCreate, request: Request, admin: Creator, db: DbSession
) -> dict[str, Any]:
    asset = await get_entity(db, VideoAsset, payload.video_asset_id, label="video asset")
    language = await require_reference(db, Language, payload.language_id, label="language")
    if payload.is_default:
        await db.execute(
            update(Subtitle)
            .where(Subtitle.video_asset_id == asset.id, Subtitle.deleted_at.is_(None))
            .values(is_default=False)
        )
    row = Subtitle(**payload.model_dump(), video_asset=asset, language=language)
    db.add(row)
    await db.flush()
    new = subtitle_data(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="subtitle.create",
        entity_type="subtitle",
        entity_id=row.id,
        old=None,
        new=new,
    )
    return success(new)


@router.patch("/subtitles/{subtitle_id}")
async def admin_update_subtitle(
    subtitle_id: UUID, payload: SubtitleUpdate, request: Request, admin: Editor, db: DbSession
) -> dict[str, Any]:
    row = await get_entity(db, Subtitle, subtitle_id, label="subtitle")
    old = subtitle_data(row)
    changes = payload.model_dump(exclude_unset=True)
    if "language_id" in changes:
        language = await require_reference(db, Language, changes["language_id"], label="language")
        if language is None:
            raise AppError("VALIDATION_ERROR", "A subtitle language is required.", status_code=422)
        row.language = language
    if changes.get("is_default"):
        await db.execute(
            update(Subtitle)
            .where(
                Subtitle.video_asset_id == row.video_asset_id,
                Subtitle.id != row.id,
                Subtitle.deleted_at.is_(None),
            )
            .values(is_default=False)
        )
    apply_model(row, payload)
    await db.flush()
    new = subtitle_data(row)
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="subtitle.update",
        entity_type="subtitle",
        entity_id=row.id,
        old=old,
        new=new,
    )
    return success(new)


@router.delete("/subtitles/{subtitle_id}")
async def admin_delete_subtitle(
    subtitle_id: UUID, request: Request, admin: Deleter, db: DbSession
) -> dict[str, Any]:
    row = await get_entity(db, Subtitle, subtitle_id, label="subtitle")
    old = subtitle_data(row)
    row.deleted_at = utcnow()
    row.is_default = False
    await _audit_commit(
        db,
        request=request,
        admin=admin,
        action="subtitle.archive",
        entity_type="subtitle",
        entity_id=row.id,
        old=old,
        new={"archived": True},
    )
    return success({"id": row.id, "archived": True})
