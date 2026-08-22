from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.deps import DbSession
from app.models.catalog import Country, Genre, Language, Tag
from app.schemas.common import success
from app.services.catalog import catalog_snapshot, list_catalog

router = APIRouter(tags=["Catalog"])
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]


def page_meta(*, page: int, limit: int, total: int) -> dict[str, int]:
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/countries")
async def countries(db: DbSession, page: Page = 1, limit: Limit = 100) -> dict[str, Any]:
    rows, total = await list_catalog(
        db,
        Country,
        page=page,
        limit=limit,
        include_inactive=False,
        order_by=(Country.sort_order, Country.name),
    )
    return success(
        [catalog_snapshot(row) for row in rows], meta=page_meta(page=page, limit=limit, total=total)
    )


@router.get("/languages")
async def languages(db: DbSession, page: Page = 1, limit: Limit = 100) -> dict[str, Any]:
    rows, total = await list_catalog(
        db,
        Language,
        page=page,
        limit=limit,
        include_inactive=False,
        order_by=(Language.sort_order, Language.name),
    )
    return success(
        [catalog_snapshot(row) for row in rows], meta=page_meta(page=page, limit=limit, total=total)
    )


@router.get("/genres")
async def genres(db: DbSession, page: Page = 1, limit: Limit = 100) -> dict[str, Any]:
    rows, total = await list_catalog(
        db,
        Genre,
        page=page,
        limit=limit,
        include_inactive=False,
        order_by=(Genre.sort_order, Genre.name),
    )
    return success(
        [catalog_snapshot(row) for row in rows], meta=page_meta(page=page, limit=limit, total=total)
    )


@router.get("/tags")
async def tags(db: DbSession, page: Page = 1, limit: Limit = 100) -> dict[str, Any]:
    rows, total = await list_catalog(
        db,
        Tag,
        page=page,
        limit=limit,
        include_inactive=False,
        order_by=Tag.name,
    )
    return success(
        [catalog_snapshot(row) for row in rows], meta=page_meta(page=page, limit=limit, total=total)
    )
