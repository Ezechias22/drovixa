# Drovixa Phase 7 — Administration

Phase 7 adds the independent, production-oriented Drovixa Admin Dashboard and
the backend operations it requires. It keeps all Phase 1–6 data, Mux settings,
payment settings, and client environment files.

## Delivered modules

- Independent responsive Next.js Admin Dashboard on port `3001`.
- Staff login through a server-side proxy; access and refresh tokens remain in
  HttpOnly, SameSite cookies and never enter browser storage.
- Dashboard metrics and operational warnings for expiring licenses, scheduled
  releases, failed video processing, payment failures, reports, and comments.
- User search, status controls, session revocation, and role assignment.
- Content list, creation, publishing, and archival entrypoints for series/movies.
- Database-backed Homepage Builder with section ordering, algorithms, manual
  content, presentation styles, schedules, country/language targeting, and
  premium/non-premium targeting.
- Notification campaign drafts, scheduling, cancellation, audience segments,
  and idempotent in-app dispatch. Celery Beat checks scheduled campaigns every
  minute. Push/email channels stay explicitly unavailable until providers exist.
- Revenue, playback, content, user, payment, subscription, and coin dashboards.
- Existing comment/report moderation integrated into the visual dashboard.
- Feature flags, remote configuration, and filterable audit logs.
- Drovixa logo assets reused in the Admin Dashboard.

## Main files

```text
admin/
├── app/(panel)/
├── app/api/
├── components/
├── lib/
├── Dockerfile
└── package.json

backend/
├── app/models/administration.py
├── app/schemas/administration.py
├── app/services/administration.py
├── app/routes/admin_operations.py
├── migrations/versions/20260822_0008_phase7_admin.py
└── tests/test_admin_operations.py
```

## Database migration

The Phase 7 migration head is:

```text
20260822_0008
```

It adds user country/language targeting fields, `homepage_sections`,
`homepage_section_items`, and `notification_campaigns`, including indexes,
constraints, and initial configurable Home sections.

## Environment additions

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
ADMIN_COOKIE_SECURE=false
```

Keep `ADMIN_COOKIE_SECURE=false` for local HTTP development. Set it to `true`
only when the Admin Dashboard is behind HTTPS in staging/production.

## Windows upgrade

Close Metro/Next terminals with `Ctrl+C`, start Docker Desktop, and install the
Phase 7 ZIP over the existing `drovixa` folder. The archive excludes `.env` and
`mobile/.env`. Never use `docker compose down -v`; it removes the database and
Redis volumes.

After extraction:

```powershell
Set-Location "C:\Users\touss\DrovixaProject\drovixa"

$DockerBin = "C:\Program Files\Docker\Docker\resources\bin"
$DockerExe = Join-Path $DockerBin "docker.exe"
$MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$DockerBin;$MachinePath;$UserPath"

npm install
& $DockerExe compose up --build -d --wait --force-recreate
& $DockerExe compose ps
& $DockerExe compose exec backend alembic current

Invoke-RestMethod "http://localhost:8000/api/v1/health/ready" |
    ConvertTo-Json -Depth 5

Start-Process "http://localhost:3001/login"
```

Alembic must print `20260822_0008 (head)`. Docker Compose must show `backend`,
`worker`, `scheduler`, `postgres`, `redis`, and `admin` running/healthy.

Sign in at `http://localhost:3001/login` with `FIRST_SUPERUSER_EMAIL` and
`FIRST_SUPERUSER_PASSWORD` from the root `.env`. Do not paste that password into
chat or terminal output.

## Verification commands

```powershell
npm run typecheck:clients
npm run build --workspace @drovixa/web
npm run build --workspace @drovixa/admin
& $DockerExe compose exec backend pytest
```

Acceptance checks:

1. Dashboard metrics load without exposing tokens in browser storage.
2. A user can be searched and suspended/restored, but the current super admin
   cannot suspend itself.
3. A Home section can be reordered or hidden and `/api/v1/home` reflects it.
4. An in-app notification campaign can be sent once without duplicate delivery.
5. Feature flags/settings update immediately and write audit records.
6. Comments/reports can be moderated from the Admin Dashboard.
7. Payment, subscription and coin data remain backend-authoritative.

## Quality checks used for this delivery

- 74 backend tests passed.
- Ruff and strict MyPy passed.
- PostgreSQL Alembic SQL generation reached `20260822_0008`.
- Mobile, public web, and admin TypeScript checks passed.
- Public Web and Admin production builds passed.
- Expo public configuration validation passed for Drovixa `0.7.0`.

Phase 8 remains responsible for the final security audit, observability,
performance/load testing, deployment pipelines, production TLS/domains,
Android/iOS release builds, and disaster-recovery rehearsal.
