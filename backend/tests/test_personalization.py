from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import utcnow
from app.models.configuration import FeatureFlag
from app.models.content import Content, Series
from app.models.enums import (
    AgeRating,
    ContentStatus,
    ContentType,
    ContentVisibility,
    Orientation,
    SeriesStatus,
)


async def enable_phase10(db: AsyncSession) -> None:
    db.add_all(
        [
            FeatureFlag(
                key=key,
                description=f"Phase 10 {key}",
                enabled=True,
                rollout_percentage=100,
                rules={},
            )
            for key in (
                "multi_profile_enabled",
                "kids_mode_enabled",
                "ratings_enabled",
                "downloads_enabled",
                "chromecast_enabled",
                "airplay_enabled",
            )
        ]
    )
    await db.commit()


async def story(db: AsyncSession, *, age_rating: AgeRating, title: str) -> Content:
    content = Content(
        type=ContentType.SERIES,
        title=title,
        slug=f"{title.casefold().replace(' ', '-')}-{uuid4().hex[:8]}",
        age_rating=age_rating,
        status=ContentStatus.PUBLISHED,
        visibility=ContentVisibility.PUBLIC,
        published_at=utcnow(),
        allowed_countries=[],
        blocked_countries=[],
    )
    series = Series(
        content=content,
        series_status=SeriesStatus.ONGOING,
        orientation=Orientation.VERTICAL,
    )
    db.add_all([content, series])
    await db.commit()
    return content


async def test_profiles_kids_filter_and_ratings(
    client: AsyncClient,
    db: AsyncSession,
    registered: dict[str, object],
) -> None:
    await enable_phase10(db)
    family = await story(db, age_rating=AgeRating.ALL, title="Family Star")
    await story(db, age_rating=AgeRating.EIGHTEEN_PLUS, title="Midnight Crime")
    headers = {"Authorization": f"Bearer {registered['access_token']}"}

    profiles = await client.get("/api/v1/profiles", headers=headers)
    assert profiles.status_code == 200, profiles.text
    assert len(profiles.json()["data"]) == 1
    assert profiles.json()["data"][0]["is_default"] is True

    created = await client.post(
        "/api/v1/profiles",
        headers=headers,
        json={
            "name": "Timoun",
            "avatar_key": "comet",
            "is_kids": True,
            "age_limit": 7,
            "pin": "2244",
            "language_code": "ht",
        },
    )
    assert created.status_code == 201, created.text
    profile = created.json()["data"]
    assert profile["is_kids"] is True
    assert profile["pin_protected"] is True

    profile_headers = {**headers, "X-Drovixa-Profile-ID": profile["id"]}
    home = await client.get("/api/v1/home", headers=profile_headers)
    assert home.status_code == 200, home.text
    titles = {
        item["title"] for section in home.json()["data"]["sections"] for item in section["items"]
    }
    assert "Family Star" in titles
    assert "Midnight Crime" not in titles

    saved = await client.put(
        f"/api/v1/ratings/{family.id}",
        headers=profile_headers,
        json={"score": 5},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["data"]["score"] == 5
    assert float(saved.json()["data"]["average"]) == 10.0
    assert saved.json()["data"]["count"] == 1

    verified = await client.post(
        f"/api/v1/profiles/{profile['id']}/verify-pin",
        headers=headers,
        json={"pin": "2244"},
    )
    assert verified.json()["data"]["valid"] is True
