# Drovixa Phase 2 — Content and Catalog

## Delivered scope

Phase 2 extends the Phase 1 foundation; it does not replace authentication,
RBAC, feature flags, remote config, Docker, or existing user data.

The database now includes:

- countries and languages;
- genres and tags;
- actors, crew members, and ordered credits;
- a shared `content` root for common series/movie metadata;
- one-to-one series and movie extensions;
- seasons and episodes;
- video-asset provider metadata and processing state;
- VTT/SRT subtitle tracks;
- content rights windows and country allow/block lists;
- soft-delete timestamps and indexes for public/admin queries.

`content` owns common title, slug, artwork, descriptions, country, language,
age rating, publication state, visibility, premium flag, rating, licensing,
SEO, genres, tags, cast, and crew. `series` and `movies` only store their
type-specific fields. This keeps one canonical record for search, discovery,
recommendations, and future analytics.

## Files added or changed

```text
backend/
├── app/
│   ├── models/
│   │   ├── catalog.py
│   │   ├── content.py
│   │   └── enums.py
│   ├── schemas/
│   │   ├── catalog.py
│   │   └── content.py
│   ├── services/
│   │   ├── catalog.py
│   │   └── content.py
│   ├── routes/
│   │   ├── catalog.py
│   │   ├── content.py
│   │   ├── admin_catalog.py
│   │   └── admin_content.py
│   └── api/router.py
├── migrations/versions/20260813_0002_phase2_content.py
└── tests/
    ├── test_catalog.py
    └── test_content.py
```

## Database migration

Migration `20260813_0002` is additive. It does not drop or rewrite Phase 1
authentication tables. It seeds an initial operational catalog:

- 8 countries;
- English, French, Brazilian Portuguese, Spanish, and Haitian Creole;
- 12 launch genres;
- 8 recommendation/search tags.

All seeded records use deterministic UUIDs. Admin users can edit, archive, or
add records through the API.

## Public API

Public list endpoints use `page` and `limit` (`20` by default for content,
maximum `100`). Public content queries only return records that are published,
public, inside their publish window, and inside their license window.

```text
GET /api/v1/countries
GET /api/v1/languages
GET /api/v1/genres
GET /api/v1/tags
GET /api/v1/content/{slug}
GET /api/v1/series
GET /api/v1/series/{slug}
GET /api/v1/series/{series_id}/episodes
GET /api/v1/movies
GET /api/v1/movies/{slug}
GET /api/v1/actors/{slug}
```

Public episode responses deliberately exclude provider asset identifiers and
playback identifiers. Phase 3 will issue playback data only after entitlement,
geo, device, and media-signing checks.

## Admin API

Admin routes are protected with the existing `content.view`, `content.create`,
`content.edit`, `content.delete`, and `content.publish` permissions. Every
successful mutation writes an audit log with the administrator, action,
entity, old/new value, IP, user agent, and timestamp.

```text
/api/v1/admin/countries
/api/v1/admin/languages
/api/v1/admin/genres
/api/v1/admin/tags
/api/v1/admin/actors
/api/v1/admin/crew
/api/v1/admin/series
/api/v1/admin/seasons
/api/v1/admin/episodes
/api/v1/admin/movies
/api/v1/admin/video-assets
/api/v1/admin/subtitles
```

Publishing a movie or episode requires an attached video asset in `ready`
state. Deleting is a soft archive. A season with active episodes and a video
asset still attached to active content cannot be archived until its dependency
is moved or archived.

## Upgrade an existing Windows Phase 1 installation

The release ZIP has a top-level `drovixa` directory and deliberately excludes
`.env`, local virtual environments, caches, test databases, and real secrets.
Extracting it over the existing project therefore preserves the local `.env`.

From PowerShell:

```powershell
Set-Location C:\Users\touss\DrovixaProject\drovixa

# Optional but recommended before a database migration.
docker compose exec -T postgres `
  pg_dump -U drovixa -d drovixa --format=plain `
  > ..\drovixa-before-phase2.sql

# This removes containers/network only. It does not remove named volumes.
docker compose down

Set-Location ..
Expand-Archive .\drovixa-phase2-content.zip `
  -DestinationPath . `
  -Force

Set-Location .\drovixa
docker compose up --build -d
```

Do not add `-v` to `docker compose down`; `-v` would delete the PostgreSQL and
Redis volumes. The backend startup command automatically runs
`alembic upgrade head` before Uvicorn starts.

No new environment variable is required in Phase 2. Keep the existing `.env`,
JWT secrets, refresh secret, and super-admin credentials.

## Verification

```powershell
docker compose ps
docker compose exec backend alembic current

Invoke-RestMethod `
  http://localhost:8000/api/v1/health/ready |
  ConvertTo-Json -Depth 5

Invoke-RestMethod `
  http://localhost:8000/api/v1/genres |
  ConvertTo-Json -Depth 5
```

`alembic current` must show `20260813_0002 (head)`. Health readiness must show
PostgreSQL and Redis as `up`; the genre response should contain the seeded
launch catalog.

## Development and quality commands

```bash
python -m pip install -r backend/requirements-dev.txt
cd backend
alembic upgrade head
ruff check app tests migrations
mypy app
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
alembic check
```

Verified delivery baseline: 33 passing tests, at least 80% branch-aware
application coverage, clean Ruff, clean strict mypy, and no Alembic model
drift.

## Deferred to Phase 3

Phase 2 does not pretend that video provider integration is complete. The
following remain Phase 3 work:

- the `VideoProvider` interface and provider adapters;
- direct upload sessions;
- signed webhook verification and processing callbacks;
- signed HLS/DASH playback authorization;
- the mobile/web player;
- progress sync, continue watching, and history.
