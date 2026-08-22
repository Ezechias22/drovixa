from __future__ import annotations

import re
import unicodedata
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.base import Base
from app.models.catalog import Actor, Country, CrewMember, Genre, Language, Tag

CatalogModel = Country | Language | Genre | Tag | Actor | CrewMember


def slugify(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")
    if not slug:
        raise AppError("VALIDATION_ERROR", "A valid slug could not be generated.", status_code=422)
    return slug


async def get_catalog_item[ModelT: CatalogModel](
    db: AsyncSession, model: type[ModelT], entity_id: UUID, *, label: str
) -> ModelT:
    row = await db.scalar(select(model).where(model.id == entity_id, model.deleted_at.is_(None)))
    if row is None:
        raise AppError("NOT_FOUND", f"The {label} was not found.", status_code=404)
    return row


async def require_reference[ModelT: CatalogModel](
    db: AsyncSession, model: type[ModelT], entity_id: UUID | None, *, label: str
) -> ModelT | None:
    if entity_id is None:
        return None
    return await get_catalog_item(db, model, entity_id, label=label)


async def ensure_unique(
    db: AsyncSession,
    model: type[Any],
    field: str,
    value: str,
    *,
    exclude_id: UUID | None = None,
) -> None:
    column = getattr(model, field)
    statement = select(model.id).where(column == value, model.deleted_at.is_(None))
    if exclude_id is not None:
        statement = statement.where(model.id != exclude_id)
    if await db.scalar(statement) is not None:
        raise AppError(
            "CONFLICT",
            f"{field.replace('_', ' ').title()} is already in use.",
            status_code=409,
        )


async def list_catalog[ModelT: CatalogModel](
    db: AsyncSession,
    model: type[ModelT],
    *,
    page: int,
    limit: int,
    include_inactive: bool,
    order_by: Any,
) -> tuple[list[ModelT], int]:
    conditions = [model.deleted_at.is_(None)]
    if not include_inactive:
        conditions.append(model.active.is_(True))
    base: Select[tuple[ModelT]] = select(model).where(*conditions)
    total = int(await db.scalar(select(func.count()).select_from(base.subquery())) or 0)
    ordering = order_by if isinstance(order_by, tuple) else (order_by,)
    rows = (
        await db.scalars(base.order_by(*ordering).offset((page - 1) * limit).limit(limit))
    ).all()
    return list(rows), total


def catalog_snapshot(row: CatalogModel) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(row.id),
        "name": row.name,
        "active": row.active,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
    if isinstance(row, Country):
        data.update(code=row.code, currency=row.currency, sort_order=row.sort_order)
    elif isinstance(row, Language):
        data.update(code=row.code, native_name=row.native_name, sort_order=row.sort_order)
    elif isinstance(row, Genre):
        data.update(
            slug=row.slug,
            icon=row.icon,
            image_url=row.image_url,
            sort_order=row.sort_order,
        )
    elif isinstance(row, Tag):
        data.update(slug=row.slug)
    else:
        data.update(
            slug=row.slug,
            photo_url=row.photo_url,
            bio=row.bio,
            country_id=str(row.country_id) if row.country_id else None,
            social_links=row.social_links,
        )
        if isinstance(row, Actor):
            data["birth_date"] = row.birth_date
    return data


def apply_changes(row: Base, changes: dict[str, Any]) -> None:
    for field, value in changes.items():
        setattr(row, field, value)
