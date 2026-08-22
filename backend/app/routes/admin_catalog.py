from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from app.api.deps import DbSession, require_permission
from app.models.catalog import Actor, Country, CrewMember, Genre, Language, Tag
from app.models.user import User
from app.schemas.catalog import (
    ActorCreate,
    ActorUpdate,
    CountryCreate,
    CountryUpdate,
    GenreCreate,
    GenreUpdate,
    LanguageCreate,
    LanguageUpdate,
    PersonCreate,
    PersonUpdate,
    TagCreate,
    TagUpdate,
)
from app.schemas.common import success
from app.services.audit import add_audit_log
from app.services.catalog import (
    CatalogModel,
    apply_changes,
    catalog_snapshot,
    ensure_unique,
    get_catalog_item,
    list_catalog,
    require_reference,
    slugify,
)

router = APIRouter(prefix="/admin", tags=["Admin catalog"])
ContentViewer = Annotated[User, require_permission("content.view")]
ContentCreator = Annotated[User, require_permission("content.create")]
ContentEditor = Annotated[User, require_permission("content.edit")]
ContentDeleter = Annotated[User, require_permission("content.delete")]
Page = Annotated[int, Query(ge=1)]
Limit = Annotated[int, Query(ge=1, le=100)]
CatalogType = (
    type[Country] | type[Language] | type[Genre] | type[Tag] | type[Actor] | type[CrewMember]
)


def _meta(page: int, limit: int, total: int) -> dict[str, int]:
    return {"page": page, "limit": limit, "total": total, "pages": (total + limit - 1) // limit}


async def _list(db: DbSession, model: CatalogType, *, page: int, limit: int) -> dict[str, Any]:
    order = getattr(model, "sort_order", None)
    order_by: Any = (order, model.name) if order is not None else model.name
    rows, total = await list_catalog(
        db,
        model,
        page=page,
        limit=limit,
        include_inactive=True,
        order_by=order_by,
    )
    return success([catalog_snapshot(row) for row in rows], meta=_meta(page, limit, total))


async def _create(
    db: DbSession,
    *,
    model: CatalogType,
    payload: BaseModel,
    request: Request,
    admin: User,
    entity_type: str,
) -> dict[str, Any]:
    values = payload.model_dump()
    if model in (Genre, Tag, Actor, CrewMember):
        values["slug"] = slugify(values.get("slug") or values["name"])
        await ensure_unique(db, model, "slug", values["slug"])
    elif model in (Country, Language):
        await ensure_unique(db, model, "code", values["code"])
    if model in (Actor, CrewMember):
        await require_reference(db, Country, values.get("country_id"), label="country")
    row: CatalogModel = model(**values)
    db.add(row)
    await db.flush()
    new = catalog_snapshot(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action=f"{entity_type}.create",
        entity_type=entity_type,
        entity_id=str(row.id),
        old_value=None,
        new_value=jsonable_encoder(new),
    )
    await db.commit()
    return success(new)


async def _update(
    db: DbSession,
    *,
    model: CatalogType,
    entity_id: UUID,
    payload: BaseModel,
    request: Request,
    admin: User,
    entity_type: str,
) -> dict[str, Any]:
    row = await get_catalog_item(db, model, entity_id, label=entity_type)
    old = catalog_snapshot(row)
    changes = payload.model_dump(exclude_unset=True)
    if "slug" in changes and changes["slug"] is not None:
        changes["slug"] = slugify(changes["slug"])
        await ensure_unique(db, model, "slug", changes["slug"], exclude_id=row.id)
    if "code" in changes and changes["code"] is not None:
        await ensure_unique(db, model, "code", changes["code"], exclude_id=row.id)
    if model in (Actor, CrewMember) and "country_id" in changes:
        await require_reference(db, Country, changes["country_id"], label="country")
    apply_changes(row, changes)
    await db.flush()
    new = catalog_snapshot(row)
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action=f"{entity_type}.update",
        entity_type=entity_type,
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder(new),
    )
    await db.commit()
    return success(new)


async def _delete(
    db: DbSession,
    *,
    model: CatalogType,
    entity_id: UUID,
    request: Request,
    admin: User,
    entity_type: str,
) -> dict[str, Any]:
    row = await get_catalog_item(db, model, entity_id, label=entity_type)
    old = catalog_snapshot(row)
    from app.models.base import utcnow

    row.deleted_at = utcnow()
    row.active = False
    add_audit_log(
        db,
        admin=admin,
        request=request,
        action=f"{entity_type}.archive",
        entity_type=entity_type,
        entity_id=str(row.id),
        old_value=jsonable_encoder(old),
        new_value=jsonable_encoder({"deleted_at": row.deleted_at, "active": False}),
    )
    await db.commit()
    return success({"id": row.id, "archived": True})


@router.get("/countries")
async def list_countries(
    _: ContentViewer, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    return await _list(db, Country, page=page, limit=limit)


@router.post("/countries", status_code=status.HTTP_201_CREATED)
async def create_country(
    payload: CountryCreate, request: Request, admin: ContentCreator, db: DbSession
) -> dict[str, Any]:
    return await _create(
        db, model=Country, payload=payload, request=request, admin=admin, entity_type="country"
    )


@router.patch("/countries/{entity_id}")
async def update_country(
    entity_id: UUID, payload: CountryUpdate, request: Request, admin: ContentEditor, db: DbSession
) -> dict[str, Any]:
    return await _update(
        db,
        model=Country,
        entity_id=entity_id,
        payload=payload,
        request=request,
        admin=admin,
        entity_type="country",
    )


@router.delete("/countries/{entity_id}")
async def delete_country(
    entity_id: UUID, request: Request, admin: ContentDeleter, db: DbSession
) -> dict[str, Any]:
    return await _delete(
        db, model=Country, entity_id=entity_id, request=request, admin=admin, entity_type="country"
    )


@router.get("/languages")
async def list_languages(
    _: ContentViewer, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    return await _list(db, Language, page=page, limit=limit)


@router.post("/languages", status_code=status.HTTP_201_CREATED)
async def create_language(
    payload: LanguageCreate, request: Request, admin: ContentCreator, db: DbSession
) -> dict[str, Any]:
    return await _create(
        db, model=Language, payload=payload, request=request, admin=admin, entity_type="language"
    )


@router.patch("/languages/{entity_id}")
async def update_language(
    entity_id: UUID, payload: LanguageUpdate, request: Request, admin: ContentEditor, db: DbSession
) -> dict[str, Any]:
    return await _update(
        db,
        model=Language,
        entity_id=entity_id,
        payload=payload,
        request=request,
        admin=admin,
        entity_type="language",
    )


@router.delete("/languages/{entity_id}")
async def delete_language(
    entity_id: UUID, request: Request, admin: ContentDeleter, db: DbSession
) -> dict[str, Any]:
    return await _delete(
        db,
        model=Language,
        entity_id=entity_id,
        request=request,
        admin=admin,
        entity_type="language",
    )


@router.get("/genres")
async def list_genres(
    _: ContentViewer, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    return await _list(db, Genre, page=page, limit=limit)


@router.post("/genres", status_code=status.HTTP_201_CREATED)
async def create_genre(
    payload: GenreCreate, request: Request, admin: ContentCreator, db: DbSession
) -> dict[str, Any]:
    return await _create(
        db, model=Genre, payload=payload, request=request, admin=admin, entity_type="genre"
    )


@router.patch("/genres/{entity_id}")
async def update_genre(
    entity_id: UUID, payload: GenreUpdate, request: Request, admin: ContentEditor, db: DbSession
) -> dict[str, Any]:
    return await _update(
        db,
        model=Genre,
        entity_id=entity_id,
        payload=payload,
        request=request,
        admin=admin,
        entity_type="genre",
    )


@router.delete("/genres/{entity_id}")
async def delete_genre(
    entity_id: UUID, request: Request, admin: ContentDeleter, db: DbSession
) -> dict[str, Any]:
    return await _delete(
        db, model=Genre, entity_id=entity_id, request=request, admin=admin, entity_type="genre"
    )


@router.get("/tags")
async def list_tags(
    _: ContentViewer, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    return await _list(db, Tag, page=page, limit=limit)


@router.post("/tags", status_code=status.HTTP_201_CREATED)
async def create_tag(
    payload: TagCreate, request: Request, admin: ContentCreator, db: DbSession
) -> dict[str, Any]:
    return await _create(
        db, model=Tag, payload=payload, request=request, admin=admin, entity_type="tag"
    )


@router.patch("/tags/{entity_id}")
async def update_tag(
    entity_id: UUID, payload: TagUpdate, request: Request, admin: ContentEditor, db: DbSession
) -> dict[str, Any]:
    return await _update(
        db,
        model=Tag,
        entity_id=entity_id,
        payload=payload,
        request=request,
        admin=admin,
        entity_type="tag",
    )


@router.delete("/tags/{entity_id}")
async def delete_tag(
    entity_id: UUID, request: Request, admin: ContentDeleter, db: DbSession
) -> dict[str, Any]:
    return await _delete(
        db, model=Tag, entity_id=entity_id, request=request, admin=admin, entity_type="tag"
    )


@router.get("/actors")
async def list_actors(
    _: ContentViewer, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    return await _list(db, Actor, page=page, limit=limit)


@router.post("/actors", status_code=status.HTTP_201_CREATED)
async def create_actor(
    payload: ActorCreate, request: Request, admin: ContentCreator, db: DbSession
) -> dict[str, Any]:
    return await _create(
        db, model=Actor, payload=payload, request=request, admin=admin, entity_type="actor"
    )


@router.patch("/actors/{entity_id}")
async def update_actor(
    entity_id: UUID, payload: ActorUpdate, request: Request, admin: ContentEditor, db: DbSession
) -> dict[str, Any]:
    return await _update(
        db,
        model=Actor,
        entity_id=entity_id,
        payload=payload,
        request=request,
        admin=admin,
        entity_type="actor",
    )


@router.delete("/actors/{entity_id}")
async def delete_actor(
    entity_id: UUID, request: Request, admin: ContentDeleter, db: DbSession
) -> dict[str, Any]:
    return await _delete(
        db, model=Actor, entity_id=entity_id, request=request, admin=admin, entity_type="actor"
    )


@router.get("/crew")
async def list_crew(
    _: ContentViewer, db: DbSession, page: Page = 1, limit: Limit = 20
) -> dict[str, Any]:
    return await _list(db, CrewMember, page=page, limit=limit)


@router.post("/crew", status_code=status.HTTP_201_CREATED)
async def create_crew(
    payload: PersonCreate, request: Request, admin: ContentCreator, db: DbSession
) -> dict[str, Any]:
    return await _create(
        db,
        model=CrewMember,
        payload=payload,
        request=request,
        admin=admin,
        entity_type="crew_member",
    )


@router.patch("/crew/{entity_id}")
async def update_crew(
    entity_id: UUID, payload: PersonUpdate, request: Request, admin: ContentEditor, db: DbSession
) -> dict[str, Any]:
    return await _update(
        db,
        model=CrewMember,
        entity_id=entity_id,
        payload=payload,
        request=request,
        admin=admin,
        entity_type="crew_member",
    )


@router.delete("/crew/{entity_id}")
async def delete_crew(
    entity_id: UUID, request: Request, admin: ContentDeleter, db: DbSession
) -> dict[str, Any]:
    return await _delete(
        db,
        model=CrewMember,
        entity_id=entity_id,
        request=request,
        admin=admin,
        entity_type="crew_member",
    )
