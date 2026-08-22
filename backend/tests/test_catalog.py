from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.audit import AuditLog
from app.models.catalog import Genre
from app.services.catalog import get_catalog_item, slugify


def test_slug_normalization_and_invalid_slug() -> None:
    assert slugify("Étoile Bleue") == "etoile-bleue"
    with pytest.raises(AppError) as captured:
        slugify("!!!")
    assert captured.value.code == "VALIDATION_ERROR"


async def test_missing_catalog_entity_has_standard_error(db: AsyncSession) -> None:
    with pytest.raises(AppError) as captured:
        await get_catalog_item(db, Genre, uuid4(), label="genre")
    assert captured.value.status_code == 404


async def test_catalog_admin_crud_and_public_lists(
    client: AsyncClient, db: AsyncSession, admin_headers: dict[str, str]
) -> None:
    country = await client.post(
        "/api/v1/admin/countries",
        headers=admin_headers,
        json={"code": "ht", "name": "Haiti", "currency": "htg", "sort_order": 1},
    )
    assert country.status_code == 201
    country_id = country.json()["data"]["id"]
    assert country.json()["data"]["code"] == "HT"

    language = await client.post(
        "/api/v1/admin/languages",
        headers=admin_headers,
        json={"code": "ht", "name": "Haitian Creole", "native_name": "Kreyòl"},
    )
    assert language.status_code == 201

    genre = await client.post(
        "/api/v1/admin/genres",
        headers=admin_headers,
        json={"name": "Romance", "icon": "heart", "sort_order": 2},
    )
    tag = await client.post(
        "/api/v1/admin/tags",
        headers=admin_headers,
        json={"name": "Secret Identity"},
    )
    actor = await client.post(
        "/api/v1/admin/actors",
        headers=admin_headers,
        json={
            "name": "Marie Jean",
            "country_id": country_id,
            "birth_date": "1998-01-02",
            "social_links": {"instagram": "https://example.com/marie"},
        },
    )
    crew = await client.post(
        "/api/v1/admin/crew",
        headers=admin_headers,
        json={"name": "Paul Director", "country_id": country_id},
    )
    assert genre.status_code == tag.status_code == actor.status_code == crew.status_code == 201
    assert genre.json()["data"]["slug"] == "romance"
    assert actor.json()["data"]["slug"] == "marie-jean"

    resources = ("countries", "languages", "genres", "tags", "actors", "crew")
    for resource in resources:
        response = await client.get(f"/api/v1/admin/{resource}", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["meta"]["total"] == 1

    updated = await client.patch(
        f"/api/v1/admin/actors/{actor.json()['data']['id']}",
        headers=admin_headers,
        json={"name": "Marie J.", "slug": "Marie J Star"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["slug"] == "marie-j-star"

    for resource in ("countries", "languages", "genres", "tags"):
        response = await client.get(f"/api/v1/{resource}")
        assert response.status_code == 200
        assert response.json()["meta"]["total"] == 1

    duplicate = await client.post(
        "/api/v1/admin/countries",
        headers=admin_headers,
        json={"code": "HT", "name": "Duplicate", "currency": "USD"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "CONFLICT"

    updates = (
        ("countries", country_id, {"name": "Republic of Haiti"}),
        ("languages", language.json()["data"]["id"], {"native_name": "Kreyòl ayisyen"}),
        ("genres", genre.json()["data"]["id"], {"icon": "heart-filled"}),
        ("tags", tag.json()["data"]["id"], {"name": "Hidden Identity"}),
        ("crew", crew.json()["data"]["id"], {"bio": "Award-winning director."}),
    )
    for resource, entity_id, payload in updates:
        response = await client.patch(
            f"/api/v1/admin/{resource}/{entity_id}", headers=admin_headers, json=payload
        )
        assert response.status_code == 200

    archived = await client.delete(
        f"/api/v1/admin/tags/{tag.json()['data']['id']}", headers=admin_headers
    )
    assert archived.status_code == 200
    public_tags = await client.get("/api/v1/tags")
    assert public_tags.json()["meta"]["total"] == 0
    archives = (
        ("actors", actor.json()["data"]["id"]),
        ("crew", crew.json()["data"]["id"]),
        ("genres", genre.json()["data"]["id"]),
        ("languages", language.json()["data"]["id"]),
        ("countries", country_id),
    )
    for resource, entity_id in archives:
        response = await client.delete(
            f"/api/v1/admin/{resource}/{entity_id}", headers=admin_headers
        )
        assert response.status_code == 200
    assert await db.scalar(select(func.count()).select_from(AuditLog)) == 18


async def test_catalog_requires_content_permissions(
    client: AsyncClient, registered: dict[str, object]
) -> None:
    response = await client.post(
        "/api/v1/admin/genres",
        headers={"Authorization": f"Bearer {registered['access_token']}"},
        json={"name": "Drama"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_catalog_validation_rejects_bad_iso_codes(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    response = await client.post(
        "/api/v1/admin/countries",
        headers=admin_headers,
        json={"code": "HAITI", "name": "Haiti", "currency": "HTG"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
