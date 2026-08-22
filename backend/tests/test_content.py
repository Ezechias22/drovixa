from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import Constraint, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.base import Base
from app.schemas.content import EpisodeCreate, SeriesCreate


async def create_catalog(client: AsyncClient, headers: dict[str, str]) -> dict[str, str]:
    country = await client.post(
        "/api/v1/admin/countries",
        headers=headers,
        json={"code": "BR", "name": "Brazil", "currency": "BRL"},
    )
    language = await client.post(
        "/api/v1/admin/languages",
        headers=headers,
        json={"code": "pt-BR", "name": "Portuguese", "native_name": "Português"},
    )
    genre = await client.post("/api/v1/admin/genres", headers=headers, json={"name": "Drama"})
    tag = await client.post("/api/v1/admin/tags", headers=headers, json={"name": "Revenge"})
    actor = await client.post("/api/v1/admin/actors", headers=headers, json={"name": "Ana Star"})
    crew = await client.post("/api/v1/admin/crew", headers=headers, json={"name": "Luis Director"})
    return {
        "country": country.json()["data"]["id"],
        "language": language.json()["data"]["id"],
        "genre": genre.json()["data"]["id"],
        "tag": tag.json()["data"]["id"],
        "actor": actor.json()["data"]["id"],
        "crew": crew.json()["data"]["id"],
    }


async def test_series_episode_asset_subtitle_and_public_flow(
    client: AsyncClient, db: AsyncSession, admin_headers: dict[str, str]
) -> None:
    refs = await create_catalog(client, admin_headers)
    series_response = await client.post(
        "/api/v1/admin/series",
        headers=admin_headers,
        json={
            "title": "The Hidden Crown",
            "description": "A royal short drama.",
            "country_id": refs["country"],
            "original_language_id": refs["language"],
            "genre_ids": [refs["genre"]],
            "tag_ids": [refs["tag"]],
            "actor_credits": [
                {
                    "actor_id": refs["actor"],
                    "character_name": "Lia",
                    "is_lead": True,
                }
            ],
            "crew_credits": [{"crew_member_id": refs["crew"], "role": "director"}],
            "orientation": "vertical",
            "series_status": "ongoing",
            "allowed_countries": ["BR", "HT"],
        },
    )
    assert series_response.status_code == 201, series_response.text
    series = series_response.json()["data"]
    series_id = series["id"]
    assert series["slug"] == "the-hidden-crown"
    assert series["cast"][0]["character_name"] == "Lia"

    assert (await client.get("/api/v1/series/the-hidden-crown")).status_code == 404
    assert (
        await client.get(f"/api/v1/admin/series/{series_id}", headers=admin_headers)
    ).status_code == 200
    admin_list = await client.get("/api/v1/admin/series", headers=admin_headers)
    assert admin_list.json()["meta"]["total"] == 1

    updated_series = await client.patch(
        f"/api/v1/admin/series/{series_id}",
        headers=admin_headers,
        json={"short_description": "A premium royal mystery.", "rating": "9.25"},
    )
    assert updated_series.status_code == 200
    assert float(updated_series.json()["data"]["rating"]) == 9.25

    season_response = await client.post(
        "/api/v1/admin/seasons",
        headers=admin_headers,
        json={"series_id": series_id, "season_number": 1, "title": "The Return"},
    )
    assert season_response.status_code == 201
    season_id = season_response.json()["data"]["id"]
    seasons = await client.get(
        "/api/v1/admin/seasons", headers=admin_headers, params={"series_id": series_id}
    )
    assert seasons.json()["meta"]["total"] == 1
    assert (
        await client.patch(
            f"/api/v1/admin/seasons/{season_id}",
            headers=admin_headers,
            json={"title": "The Royal Return", "sort_order": 1},
        )
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/admin/seasons/{season_id}/publish", headers=admin_headers)
    ).status_code == 200

    asset_response = await client.post(
        "/api/v1/admin/video-assets",
        headers=admin_headers,
        json={
            "provider": "mux",
            "provider_asset_id": "mux-episode-1",
            "status": "processing",
            "aspect_ratio": "9:16",
            "metadata": {"source": "direct-upload"},
        },
    )
    assert asset_response.status_code == 201
    asset_id = asset_response.json()["data"]["id"]
    assets = await client.get("/api/v1/admin/video-assets", headers=admin_headers)
    assert assets.json()["meta"]["total"] == 1

    episode_response = await client.post(
        "/api/v1/admin/episodes",
        headers=admin_headers,
        json={
            "series_id": series_id,
            "season_id": season_id,
            "episode_number": 1,
            "title": "The Secret",
            "video_asset_id": asset_id,
            "orientation": "vertical",
            "access_type": "premium_or_coin",
            "coin_price": 20,
        },
    )
    assert episode_response.status_code == 201, episode_response.text
    episode_id = episode_response.json()["data"]["id"]
    assert (
        await client.get(f"/api/v1/admin/episodes/{episode_id}", headers=admin_headers)
    ).status_code == 200
    episodes = await client.get(
        "/api/v1/admin/episodes", headers=admin_headers, params={"series_id": series_id}
    )
    assert episodes.json()["meta"]["total"] == 1

    not_ready = await client.post(
        f"/api/v1/admin/episodes/{episode_id}/publish", headers=admin_headers
    )
    assert not_ready.status_code == 409
    assert not_ready.json()["error"]["code"] == "VIDEO_NOT_READY"
    ready = await client.patch(
        f"/api/v1/admin/video-assets/{asset_id}",
        headers=admin_headers,
        json={"status": "ready", "duration_seconds": 92, "width": 1080, "height": 1920},
    )
    assert ready.status_code == 200
    assert (
        await client.patch(
            f"/api/v1/admin/episodes/{episode_id}",
            headers=admin_headers,
            json={"title": "The Secret Revealed"},
        )
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/admin/episodes/{episode_id}/publish", headers=admin_headers)
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/admin/series/{series_id}/publish", headers=admin_headers)
    ).status_code == 200

    public_detail = await client.get("/api/v1/series/the-hidden-crown")
    assert public_detail.status_code == 200
    assert public_detail.json()["data"]["total_episodes"] == 1
    assert (await client.get("/api/v1/content/the-hidden-crown")).status_code == 200
    assert (await client.get("/api/v1/movies/the-hidden-crown")).status_code == 404
    assert (await client.get("/api/v1/series")).json()["meta"]["total"] == 1
    public_episodes = await client.get(f"/api/v1/series/{series_id}/episodes")
    assert public_episodes.json()["meta"]["total"] == 1
    assert "video_asset" not in public_episodes.json()["data"][0]
    filtered_episodes = await client.get(
        f"/api/v1/series/{series_id}/episodes",
        params={"season_id": season_id, "newest": True},
    )
    assert filtered_episodes.json()["meta"]["total"] == 1
    actor = await client.get("/api/v1/actors/ana-star")
    assert actor.status_code == 200
    assert actor.json()["data"]["content"][0]["slug"] == "the-hidden-crown"
    assert (await client.get("/api/v1/actors/missing-actor")).status_code == 404

    subtitle = await client.post(
        "/api/v1/admin/subtitles",
        headers=admin_headers,
        json={
            "video_asset_id": asset_id,
            "language_id": refs["language"],
            "label": "Português",
            "format": "vtt",
            "file_url": "https://cdn.example.com/subtitles/episode-1.vtt",
            "is_default": True,
        },
    )
    assert subtitle.status_code == 201, subtitle.text
    subtitle_id = subtitle.json()["data"]["id"]
    subtitle_list = await client.get(
        "/api/v1/admin/subtitles",
        headers=admin_headers,
        params={"video_asset_id": asset_id},
    )
    assert subtitle_list.json()["meta"]["total"] == 1
    assert (
        await client.patch(
            f"/api/v1/admin/subtitles/{subtitle_id}",
            headers=admin_headers,
            json={"label": "Português (Brasil)"},
        )
    ).status_code == 200
    assert (
        await client.delete(f"/api/v1/admin/subtitles/{subtitle_id}", headers=admin_headers)
    ).status_code == 200

    conflict = await client.delete(f"/api/v1/admin/video-assets/{asset_id}", headers=admin_headers)
    assert conflict.status_code == 409
    season_conflict = await client.delete(
        f"/api/v1/admin/seasons/{season_id}", headers=admin_headers
    )
    assert season_conflict.status_code == 409
    assert (
        await client.delete(f"/api/v1/admin/episodes/{episode_id}", headers=admin_headers)
    ).status_code == 200
    assert (
        await client.delete(f"/api/v1/admin/seasons/{season_id}", headers=admin_headers)
    ).status_code == 200
    assert (
        await client.delete(f"/api/v1/admin/series/{series_id}", headers=admin_headers)
    ).status_code == 200
    assert (await client.get("/api/v1/series/the-hidden-crown")).status_code == 404
    assert (await db.scalar(select(func.count()).select_from(AuditLog)) or 0) >= 20


async def test_movie_requires_ready_video_and_can_be_published(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    asset = await client.post(
        "/api/v1/admin/video-assets",
        headers=admin_headers,
        json={
            "provider": "cloudflare_stream",
            "provider_asset_id": "movie-001",
            "status": "processing",
        },
    )
    asset_id = asset.json()["data"]["id"]
    duplicate_asset = await client.post(
        "/api/v1/admin/video-assets",
        headers=admin_headers,
        json={
            "provider": "cloudflare_stream",
            "provider_asset_id": "movie-001",
            "status": "processing",
        },
    )
    assert duplicate_asset.status_code == 409
    assert duplicate_asset.json()["error"]["code"] == "CONFLICT"
    movie = await client.post(
        "/api/v1/admin/movies",
        headers=admin_headers,
        json={
            "title": "Midnight Promise",
            "video_asset_id": asset_id,
            "duration_seconds": 5400,
            "access_type": "premium_subscription",
        },
    )
    assert movie.status_code == 201
    movie_id = movie.json()["data"]["id"]
    invalid_update = await client.patch(
        f"/api/v1/admin/movies/{movie_id}",
        headers=admin_headers,
        json={"access_type": "coin_unlock", "coin_price": 0},
    )
    assert invalid_update.status_code == 422
    assert (await client.get("/api/v1/admin/movies", headers=admin_headers)).json()["meta"][
        "total"
    ] == 1
    assert (
        await client.get(f"/api/v1/admin/movies/{movie_id}", headers=admin_headers)
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/admin/movies/{movie_id}/publish", headers=admin_headers)
    ).status_code == 409
    await client.patch(
        f"/api/v1/admin/video-assets/{asset_id}",
        headers=admin_headers,
        json={"status": "ready", "playback_id": "signed-playback-id"},
    )
    assert (
        await client.patch(
            f"/api/v1/admin/movies/{movie_id}",
            headers=admin_headers,
            json={"short_description": "A cinematic promise."},
        )
    ).status_code == 200
    assert (
        await client.post(f"/api/v1/admin/movies/{movie_id}/publish", headers=admin_headers)
    ).status_code == 200
    assert (await client.get("/api/v1/movies/midnight-promise")).status_code == 200
    assert (await client.get("/api/v1/series/midnight-promise")).status_code == 404
    assert (await client.get("/api/v1/content/midnight-promise")).status_code == 200
    assert (await client.get("/api/v1/movies")).json()["meta"]["total"] == 1
    assert (
        await client.delete(f"/api/v1/admin/movies/{movie_id}", headers=admin_headers)
    ).status_code == 200

    unused = await client.post(
        "/api/v1/admin/video-assets",
        headers=admin_headers,
        json={"provider": "mux", "provider_asset_id": "unused"},
    )
    assert (
        await client.delete(
            f"/api/v1/admin/video-assets/{unused.json()['data']['id']}",
            headers=admin_headers,
        )
    ).status_code == 200


async def test_content_validation_and_permissions(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    invalid = await client.post(
        "/api/v1/admin/movies",
        headers=admin_headers,
        json={"title": "Coin Film", "access_type": "coin_unlock", "coin_price": 0},
    )
    assert invalid.status_code == 422
    forbidden = await client.post(
        "/api/v1/admin/series",
        json={"title": "Forbidden"},
    )
    assert forbidden.status_code == 401

    missing_id = uuid4()
    assert (
        await client.get(f"/api/v1/admin/series/{missing_id}", headers=admin_headers)
    ).status_code == 404
    assert (await client.get(f"/api/v1/series/{missing_id}/episodes")).status_code == 404
    assert (
        await client.get(f"/api/v1/admin/movies/{missing_id}", headers=admin_headers)
    ).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/admin/video-assets/{missing_id}",
            headers=admin_headers,
            json={"status": "ready"},
        )
    ).status_code == 404


def test_content_rights_and_episode_date_validation() -> None:
    try:
        SeriesCreate(
            title="Invalid rights",
            license_start="2026-08-20T00:00:00Z",
            license_end="2026-08-19T00:00:00Z",
        )
    except ValidationError as exc:
        assert "license_end" in str(exc)
    else:
        raise AssertionError("Invalid license dates must be rejected")

    try:
        SeriesCreate(
            title="Overlapping rights",
            allowed_countries=["HT"],
            blocked_countries=["HT"],
        )
    except ValidationError as exc:
        assert "both allowed and blocked" in str(exc)
    else:
        raise AssertionError("Overlapping country rights must be rejected")

    try:
        EpisodeCreate(
            series_id=uuid4(),
            episode_number=1,
            title="Invalid free window",
            free_from="2026-09-02T00:00:00Z",
            free_until="2026-09-01T00:00:00Z",
        )
    except ValidationError as exc:
        assert "free_until" in str(exc)
    else:
        raise AssertionError("Invalid free dates must be rejected")


def test_database_constraint_names_are_globally_unique() -> None:
    """PostgreSQL requires named relations to be unique inside a schema."""
    names = [
        constraint.name
        for table in Base.metadata.sorted_tables
        for constraint in table.constraints
        if isinstance(constraint, Constraint) and constraint.name is not None
    ]

    assert len(names) == len(set(names))
