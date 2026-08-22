# Drovixa Phase 3 — Secure Streaming

> Phase 3.1 now selects Mux Video by default. Use `PHASE_3_1_MUX.md` for the
> active setup and Windows upgrade. This document keeps the original
> Cloudflare Stream adapter instructions because the provider abstraction still
> supports it when `VIDEO_PROVIDER=cloudflare_stream` is selected explicitly.

## Delivered scope

Phase 3 extends the existing Phase 1/2 database and API. It does not replace
authentication, RBAC, content management, feature flags, or existing user data.

The implementation contains:

- a provider-neutral asynchronous `VideoProvider` interface;
- a real Cloudflare Stream adapter for direct upload, URL ingest, metadata,
  deletion, signed playback, thumbnails, and webhooks;
- one-time direct uploads with automatic basic/TUS selection;
- MIME, extension, size, and duration validation before provider calls;
- webhook HMAC-SHA256 verification, replay tolerance, raw event retention, and
  database-backed idempotency;
- server-side license, publication, geo, guest, premium, entitlement, asset,
  and simultaneous-device checks;
- locally generated, short-lived RS256 HLS/DASH tokens—no raw premium URL;
- playback sessions, authenticated progress sync, completion calculation,
  unique valid-view counting, continue watching, and soft-deleted history;
- an Expo Router / `expo-video` native player foundation for Android, iOS, and
  tablet, including native controls, seek, fullscreen, and Picture-in-Picture;
- a Next.js / `hls.js` browser player foundation with native Safari HLS,
  adaptive quality selection, VTT tracks, and progress synchronization;
- npm workspaces, lockfile, EAS profiles, and separate backend/client CI gates.

Provider credentials are never returned to a client. The admin upload API
returns only the provider's one-time upload URL and required upload headers.

## Main files added or changed

```text
drovixa/
├── package.json
├── package-lock.json
├── .github/workflows/client-ci.yml
├── mobile/
│   ├── app/_layout.tsx
│   ├── app/watch/[id].tsx
│   ├── src/api/client.ts
│   ├── src/features/player/
│   ├── src/services/device.ts
│   ├── src/stores/auth-store.ts
│   ├── app.json
│   └── eas.json
├── web/
│   ├── app/watch/[id]/page.tsx
│   ├── features/player/
│   ├── lib/api.ts
│   └── stores/auth-store.ts
└── backend/
    ├── app/integrations/videos/
    │   ├── base.py
    │   ├── cloudflare.py
    │   └── factory.py
    ├── app/models/streaming.py
    ├── app/schemas/streaming.py
    ├── app/services/streaming.py
    ├── app/services/videos.py
    ├── app/routes/admin_streaming.py
    ├── app/routes/streaming.py
    ├── app/routes/video_webhooks.py
    ├── migrations/versions/20260813_0003_phase3_streaming.py
    └── tests/test_streaming.py
```

## Database migration

Migration `20260813_0003` is additive. It adds provider error/readiness fields
to `video_assets` and creates:

- `video_upload_sessions`;
- `video_webhook_events`;
- `user_entitlements` (the access foundation used by Phase 5 monetization);
- `playback_sessions`;
- `watch_progress`;
- `watch_history`.

The migration contains lookup and active-session indexes, partial unique
indexes for one progress record per user/episode or user/movie, check
constraints, named foreign keys, a complete downgrade, and no destructive
change to Phase 1/2 tables.

## Environment variables

The application starts without Cloudflare credentials so auth/catalog work can
continue. Upload and signed playback correctly return a structured `503` until
the provider is configured.

```dotenv
VIDEO_PROVIDER=cloudflare_stream
VIDEO_API_TIMEOUT_SECONDS=20
VIDEO_UPLOAD_MAX_BYTES=10737418240
VIDEO_UPLOAD_MAX_DURATION_SECONDS=14400
VIDEO_PLAYBACK_TOKEN_TTL_SECONDS=900
VIDEO_WEBHOOK_TOLERANCE_SECONDS=300
VIDEO_ALLOWED_ORIGINS=[]

CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_STREAM_API_TOKEN=
CLOUDFLARE_STREAM_CUSTOMER_CODE=
CLOUDFLARE_STREAM_SIGNING_KEY_ID=
CLOUDFLARE_STREAM_SIGNING_KEY_PEM_B64=
CLOUDFLARE_STREAM_WEBHOOK_SECRET=

WATCH_COMPLETION_PERCENTAGE=90
PROGRESS_SYNC_INTERVAL_SECONDS=15
MINIMUM_VIEW_SECONDS=7
DEFAULT_SIMULTANEOUS_STREAM_LIMIT=1
PREMIUM_SIMULTANEOUS_STREAM_LIMIT=2
GEO_COUNTRY_HEADER=CF-IPCountry
```

`VIDEO_ALLOWED_ORIGINS` contains domain names, not URL paths. For example:

```dotenv
VIDEO_ALLOWED_ORIGINS=["app.drovixa.com","*.drovixa.com"]
```

Client environment files:

```dotenv
# mobile/.env
EXPO_PUBLIC_API_URL=http://192.168.1.10:8000/api/v1

# web/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

A physical phone cannot use the computer's `localhost`; use the computer's LAN
IPv4 address during local mobile development.

## Configure Cloudflare Stream

Create a Cloudflare API token with `Stream Write`, note the account ID and the
customer code from Stream, then use PowerShell. Keep the token and returned PEM
secret out of source control.

```powershell
$AccountId = "YOUR_CLOUDFLARE_ACCOUNT_ID"
$ApiToken = "YOUR_CLOUDFLARE_STREAM_API_TOKEN"
$CfHeaders = @{ Authorization = "Bearer $ApiToken" }

$SigningKey = Invoke-RestMethod `
  -Method Post `
  -Uri "https://api.cloudflare.com/client/v4/accounts/$AccountId/stream/keys" `
  -Headers $CfHeaders

$SigningKey.result.id
$SigningKey.result.pem
```

Cloudflare returns `pem` already base64-encoded and displays the private key
only once. Put `result.id` into `CLOUDFLARE_STREAM_SIGNING_KEY_ID` and
`result.pem` directly into `CLOUDFLARE_STREAM_SIGNING_KEY_PEM_B64`.

In staging/production, register the public webhook URL:

```powershell
$WebhookUrl = "https://api.drovixa.com/api/v1/webhooks/videos/cloudflare_stream"
$WebhookBody = @{ notificationUrl = $WebhookUrl } | ConvertTo-Json

$Webhook = Invoke-RestMethod `
  -Method Put `
  -Uri "https://api.cloudflare.com/client/v4/accounts/$AccountId/stream/webhook" `
  -Headers $CfHeaders `
  -ContentType "application/json" `
  -Body $WebhookBody

$Webhook.result.secret
$ApiToken = $null
```

Put `result.secret` into `CLOUDFLARE_STREAM_WEBHOOK_SECRET`. Cloudflare accepts
only one Stream webhook subscription per account and cannot send a webhook to
localhost; use a public staging API or a temporary tunnel for local webhook
testing.

After editing `.env`, recreate the backend so Compose injects the new values:

```powershell
$DockerExe = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
& $DockerExe compose up --build -d --wait
```

## Upload workflow

The admin authenticates normally and calls:

```text
POST /api/v1/admin/video-assets/upload-sessions
```

Example request:

```json
{
  "file_name": "episode-01.mp4",
  "content_type": "video/mp4",
  "file_size_bytes": 524288000,
  "max_duration_seconds": 900,
  "protocol": "auto"
}
```

`auto` uses basic upload up to 200 MB and resumable TUS above 200 MB. The admin
client uploads bytes directly to the one-time `upload_url`; it does not relay a
large video through FastAPI. Cloudflare processes the asset and calls the
signed webhook. Only an asset in `ready` state can be attached to published,
playable content.

For a video already accessible through a private, short-lived HTTPS source URL:

```text
POST /api/v1/admin/video-assets/ingest
POST /api/v1/admin/video-assets/{asset_id}/refresh
DELETE /api/v1/admin/video-assets/{asset_id}/provider
```

Provider deletion is blocked while an active episode or movie still references
the asset. All successful admin mutations are audited, and the one-time upload
URL is excluded from the audit payload.

## Playback and watch-state API

```text
POST   /api/v1/playback/episodes/{episode_id}/authorize
POST   /api/v1/playback/movies/{movie_id}/authorize
POST   /api/v1/playback/{episode_id}/authorize       # compatibility route
POST   /api/v1/progress
GET    /api/v1/continue-watching?page=1&limit=20
DELETE /api/v1/continue-watching/{progress_id}
POST   /api/v1/continue-watching/{progress_id}/restart
GET    /api/v1/history?page=1&limit=20
DELETE /api/v1/history/{history_id}
DELETE /api/v1/history                               # body: {"confirmation":"clear"}
```

Authorization order is deliberate: content status and license, geo rules,
access type/entitlement, video readiness/provider, then simultaneous device
limit. The returned HLS/DASH manifests expire according to
`VIDEO_PLAYBACK_TOKEN_TTL_SECONDS`. Guests may watch free content only when
guest mode is active, and they do not sync account history.

In production, expose FastAPI only through the trusted CDN/load balancer and
configure it to overwrite (not append user-supplied) `CF-IPCountry` and
`X-Forwarded-For`. Geo and IP decisions must never trust headers received from
an untrusted direct client.

The player calls `/progress` every configured interval for authenticated users.
The server clamps position to duration, marks completion at the configured
percentage, and counts one view per playback session only after the minimum
watch threshold.

## Upgrade an existing Windows Phase 2 installation

The ZIP has a top-level `drovixa` directory and excludes `.env`, databases,
virtual environments, caches, node modules, and real secrets. Extracting over
the current project preserves the existing `.env` and named Docker volumes.

```powershell
$DockerExe = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
$ProjectRoot = "C:\Users\touss\DrovixaProject"
$ProjectDir = Join-Path $ProjectRoot "drovixa"
$ZipFile = "$env:USERPROFILE\Downloads\drovixa-phase3-streaming.zip"

if (-not (Test-Path $ZipFile)) { throw "ZIP Phase 3 la pa jwenn." }

Set-Location $ProjectDir

# Backup before migration.
& $DockerExe compose exec -T postgres `
  pg_dump -U drovixa -d drovixa --format=custom `
  --file=/tmp/drovixa-before-phase3.dump
if ($LASTEXITCODE -ne 0) { throw "Backup PostgreSQL la echwe." }

& $DockerExe compose cp `
  postgres:/tmp/drovixa-before-phase3.dump `
  ..\drovixa-before-phase3.dump
if (-not (Test-Path ..\drovixa-before-phase3.dump)) {
  throw "Fichye backup la pa jwenn. Pa kontinye."
}

# Do not add -v: named volumes must remain intact.
& $DockerExe compose down

Set-Location $ProjectRoot
Expand-Archive $ZipFile -DestinationPath . -Force

Set-Location $ProjectDir
& $DockerExe compose up --build -d --wait
& $DockerExe compose ps
& $DockerExe compose exec backend alembic current
```

`alembic current` must show `20260813_0003 (head)`. If Cloudflare credentials
are not ready, leave the new secret variables blank; health, auth, and catalog
continue to work while provider-dependent routes fail closed.

## Verification commands

```powershell
$BaseUrl = "http://localhost:8000/api/v1"

Invoke-RestMethod "$BaseUrl/health/ready" |
  ConvertTo-Json -Depth 5

Start-Process "http://localhost:8000/docs"
```

To install and validate client code on Windows:

```powershell
Set-Location C:\Users\touss\DrovixaProject\drovixa
npm ci
npm run typecheck:clients
npm run build --workspace @drovixa/web

Copy-Item mobile\.env.example mobile\.env
Copy-Item web\.env.example web\.env.local
npm run web
# In another terminal: npm run mobile
```

The watch routes are `/watch/{episode_uuid}` and
`/watch/{movie_uuid}?type=movie`. They require published content with a ready
real provider asset; no fake balance, fake entitlement, or public MP4 fallback
is included.

## Development quality gates

```bash
python -m pip install -r backend/requirements-dev.txt
cd backend
ruff check app tests migrations
mypy app
pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=80
alembic upgrade head
alembic check

cd ..
npm ci
npm run typecheck:clients
npm run build --workspace @drovixa/web
EXPO_NO_TELEMETRY=1 npm exec --workspace @drovixa/mobile -- expo config --type public
```

At this release date, `npm audit` also reports upstream advisories through the
Expo 57 Metro/config toolchain (`image-size` and `uuid`). npm's proposed forced
remediation downgrades Expo across SDK generations, so it is intentionally not
applied. These packages process trusted project/build inputs rather than API or
payment traffic. Keep Dependabot enabled and take the compatible Expo patch as
soon as the SDK publishes it.

## Deliberately deferred

Phase 3 creates `user_entitlements` so access checks are real, but it does not
invent purchases. Wallet-ledger transactions, coin unlock creation,
subscriptions, receipt verification, and payments remain Phase 5. Phase 4 will
connect the broader Home/Discover/Search/detail UX to these playback routes.
Full download DRM, Chromecast, AirPlay, and multi-audio remain in their planned
later phases. SRT metadata remains supported by the catalog; browser playback
exposes VTT directly, while mobile subtitles should be packaged into the HLS
asset by the video provider.

## Primary implementation references

- [Cloudflare Stream direct creator uploads](https://developers.cloudflare.com/stream/uploading-videos/direct-creator-uploads/)
- [Cloudflare Stream signed URLs and signing keys](https://developers.cloudflare.com/stream/viewing-videos/securing-your-stream/)
- [Cloudflare Stream webhook verification](https://developers.cloudflare.com/stream/manage-video-library/using-webhooks/)
- [Expo Video](https://docs.expo.dev/versions/latest/sdk/video/)
- [Next.js video guide](https://nextjs.org/docs/app/guides/videos)
