# Drovixa Phase 6 — Community and moderation

Phase 6 adds production-oriented community features to the existing Phase 1–5
monorepo. It does not replace Mux, payment configuration, or any existing data.

## Delivered modules

- Generic likes for content, episodes, and vertical Shorts.
- Comments on content, episodes, and Shorts.
- One-level replies, spoiler marking, comment likes, edit/delete-own rules.
- Configurable report reasons and reports for comments, users, content,
  episodes, videos, subtitles, and technical issues.
- Moderator hide, delete, restore, spam, pin, and unpin actions.
- Temporary/permanent comment mutes, user bans, and user restoration.
- Comment reply/like notifications honoring notification preferences.
- Granular `comments.moderate` and `reports.manage` authorization.
- Audit records for critical moderation actions.
- Responsive community UI in Expo mobile and Next.js web.
- Server and client enforcement of `comments_enabled`.

The independent visual Admin Dashboard is finalized in Phase 7. Phase 6 already
provides the protected, paginated moderation APIs that dashboard will consume.

## Main files

```text
backend/
├── app/models/community.py
├── app/schemas/community.py
├── app/services/community.py
├── app/routes/community.py
├── app/routes/admin_community.py
├── migrations/versions/20260821_0007_phase6_community.py
└── tests/test_community.py

mobile/
├── src/features/community/
├── src/features/catalog/ContentDetailScreen.tsx
├── app/(tabs)/shorts.tsx
└── app/watch/[id].tsx

web/
├── features/community/
├── features/detail/ContentDetailExperience.tsx
├── features/shorts/ShortsExperience.tsx
└── features/player/WatchExperience.tsx
```

## Database migration

The Phase 6 head is:

```text
20260821_0007
```

It adds `likes`, `comments`, `comment_likes`, `report_reasons`, `reports`, and
`user_mutes`, their indexes and enums, seeds report reasons, and enables the
comments feature flag. Transactional data uses soft/status deletion; it is not
hard-deleted by ordinary user or moderator actions.

## Public API

```text
GET    /api/v1/likes
POST   /api/v1/likes
DELETE /api/v1/likes

GET    /api/v1/comments
POST   /api/v1/comments
GET    /api/v1/comments/{id}/replies
PATCH  /api/v1/comments/{id}
DELETE /api/v1/comments/{id}
POST   /api/v1/comments/{id}/like
DELETE /api/v1/comments/{id}/like
POST   /api/v1/comments/{id}/report

GET    /api/v1/report-reasons
POST   /api/v1/reports
```

## Moderation API

```text
GET    /api/v1/admin/comments
PATCH  /api/v1/admin/comments/{id}
GET    /api/v1/admin/reports
PATCH  /api/v1/admin/reports/{id}
POST   /api/v1/admin/users/{id}/mute
DELETE /api/v1/admin/users/{id}/mute
POST   /api/v1/admin/users/{id}/ban
POST   /api/v1/admin/users/{id}/restore
```

## Windows upgrade

Stop Metro/Next with `Ctrl+C`, start Docker Desktop, then run the installation
script supplied with the ZIP. Do not use `docker compose down -v`; `-v` removes
PostgreSQL and Redis volumes. The archive intentionally excludes `.env`, so the
existing Mux and payment credentials remain intact.

After extraction:

```powershell
Set-Location "C:\Users\touss\DrovixaProject\drovixa"
npm install
docker compose up --build -d --wait --force-recreate
docker compose exec backend alembic current
Invoke-RestMethod "http://localhost:8000/api/v1/health/ready" |
  ConvertTo-Json -Depth 5
```

The Alembic command must print `20260821_0007 (head)`.

## Client verification

Web:

```powershell
npm run dev --workspace @drovixa/web
```

Mobile (the existing `mobile/.env` must still point to the computer LAN IP):

```powershell
npm run start --workspace @drovixa/mobile -- --clear
```

Verify that a signed-in viewer can create, reply to, like, edit, delete, and
report a comment. Verify that guest viewers can read comments but are sent to
login for protected actions. Disable `comments_enabled` from the admin API and
confirm the full comments UI disappears and comment routes return
`COMMENTS_DISABLED`.

## Quality checks used for this delivery

```bash
cd backend
ruff check app tests
mypy app
pytest

cd ..
npm run typecheck:clients
npm run build --workspace @drovixa/web
```

The delivery was validated with 70 backend tests, strict backend type checking,
both client type checks, a Next.js production build, and an Expo web export.
