# Drovixa Phase 3.1 — Mux Video Provider

Phase 3.1 changes the active video provider from Cloudflare Stream to Mux Video
without removing the provider abstraction or any Phase 1–3 data. Mux is the
default; Cloudflare remains an optional adapter.

## Delivered scope

- authenticated Mux Video API requests using HTTP Basic auth;
- URL ingest and provider metadata refresh;
- Mux Direct Upload URLs with resumable `PUT` uploads;
- `passthrough`/`meta.external_id` correlation from the local UUID to Mux upload,
  asset, and playback IDs;
- out-of-order webhook protection so a delayed `created` event cannot move a
  ready asset backward to processing;
- `Mux-Signature` HMAC-SHA256 verification with replay tolerance;
- database-backed webhook idempotency and raw event retention;
- `signed` playback policies and server-only RS256 JWT generation;
- signed HLS URLs and signed thumbnail URLs;
- Basic video quality and 1080p maximum resolution by default;
- production validation for Mux credentials and a non-wildcard upload origin;
- an additive migration for the generic `resumable` upload protocol.

Mux playback remains protected by Drovixa authorization checks for
authentication, entitlement, content rights, geo availability, asset readiness,
and simultaneous device limits before a short-lived token is returned.

## Files added or changed

```text
backend/
├── app/core/config.py
├── app/integrations/videos/
│   ├── base.py
│   ├── cloudflare.py
│   ├── factory.py
│   └── mux.py
├── app/models/enums.py
├── app/routes/video_webhooks.py
├── app/schemas/streaming.py
├── app/services/streaming.py
├── app/services/videos.py
├── migrations/versions/20260813_0004_phase3_mux.py
├── tests/test_mux_video.py
├── tests/test_security_and_infra.py
└── tests/test_streaming.py

.env.example
backend/.env.example
README.md
docs/PHASE_3.md
docs/PHASE_3_1_MUX.md
```

## Database migration

`20260813_0004` adds `resumable` to the existing PostgreSQL
`upload_protocol` enum. It does not delete or rewrite user, content, auth,
watch-history, or video records.

The downgrade refuses to run while resumable sessions exist, because silently
deleting transactional upload history would be unsafe.

## Create the Mux credentials

Use one Mux environment for all three credential groups below. Do not mix a
Development access token with a Production signing key or webhook.

1. Open `https://dashboard.mux.com` and select the environment Drovixa will use.
2. In **Settings → Access Tokens**, create an access token and securely save:
   - Token ID;
   - Token Secret.
3. In **Settings → Signing Keys**, create a signing key and securely save:
   - Signing Key ID;
   - private key value. Mux exposes the private key only at creation time.
4. In **Settings → Webhooks**, add this public endpoint:

   ```text
   https://api.your-domain.com/api/v1/webhooks/videos/mux
   ```

   Save the signing secret for that endpoint.

Mux cannot call a localhost webhook. Local upload testing can use the protected
status-refresh endpoint and does not require a tunnel. Configure the public
webhook in staging and production.

## Environment variables

Open the existing `.env` in Notepad. Replace any old `VIDEO_PROVIDER` line and
add the Mux values. Never send these values in chat, commit them, or put them in
the web/mobile source.

```powershell
Set-Location C:\Users\touss\DrovixaProject\drovixa
notepad .env
```

```dotenv
VIDEO_PROVIDER=mux
MUX_TOKEN_ID=YOUR_MUX_TOKEN_ID
MUX_TOKEN_SECRET=YOUR_MUX_TOKEN_SECRET
MUX_SIGNING_KEY_ID=YOUR_MUX_SIGNING_KEY_ID
MUX_SIGNING_PRIVATE_KEY_B64=YOUR_BASE64_PRIVATE_KEY
MUX_WEBHOOK_SECRET=YOUR_MUX_WEBHOOK_SIGNING_SECRET
MUX_UPLOAD_CORS_ORIGIN=*
MUX_UPLOAD_TIMEOUT_SECONDS=21600
MUX_VIDEO_QUALITY=basic
MUX_MAX_RESOLUTION_TIER=1080p
```

`MUX_UPLOAD_CORS_ORIGIN=*` is acceptable only for local development. In staging
or production, use the exact admin origin, for example:

```dotenv
MUX_UPLOAD_CORS_ORIGIN=https://admin.drovixa.com
```

If Mux gives you a PEM file instead of an already-base64 value, convert it and
send the result directly to the Windows clipboard without printing it:

```powershell
$PemFile = "$env:USERPROFILE\Downloads\mux-signing-key.pem"
$MuxPrivateKeyB64 = [Convert]::ToBase64String(
    [IO.File]::ReadAllBytes($PemFile)
)
$MuxPrivateKeyB64 | Set-Clipboard
$MuxPrivateKeyB64 = $null
```

Paste the clipboard value after `MUX_SIGNING_PRIVATE_KEY_B64=` on one line.

## Upgrade an existing Windows Phase 3 installation

The delivery ZIP has a top-level `drovixa` directory and excludes `.env`, real
secrets, Docker volumes, caches, and `node_modules`.

First open Docker Desktop. Then run this in a fresh PowerShell window:

```powershell
$ProjectRoot = "C:\Users\touss\DrovixaProject"
$ProjectDir = Join-Path $ProjectRoot "drovixa"
$ZipFile = "$env:USERPROFILE\Downloads\drovixa-phase3.1-mux.zip"
$DockerBin = "C:\Program Files\Docker\Docker\resources\bin"
$DockerExe = Join-Path $DockerBin "docker.exe"

$MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$DockerBin;$MachinePath;$UserPath"

if (-not (Test-Path $ZipFile)) { throw "ZIP Phase 3.1 la pa jwenn." }
if (-not (Test-Path $DockerExe)) { throw "docker.exe pa jwenn." }

Set-Location $ProjectDir

& $DockerExe compose exec -T postgres `
    pg_dump -U drovixa -d drovixa `
    --format=custom `
    --file=/tmp/drovixa-before-phase31.dump
if ($LASTEXITCODE -ne 0) { throw "Backup PostgreSQL la echwe." }

& $DockerExe compose cp `
    "postgres:/tmp/drovixa-before-phase31.dump" `
    "..\drovixa-before-phase31.dump"
if (-not (Test-Path "..\drovixa-before-phase31.dump")) {
    throw "Fichye backup la pa jwenn."
}

& $DockerExe compose down

Set-Location $ProjectRoot
Expand-Archive $ZipFile -DestinationPath . -Force

Set-Location $ProjectDir
notepad .env
```

After saving the Mux variables in `.env`, continue:

```powershell
& $DockerExe compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "Docker Compose config la pa valid." }

& $DockerExe compose up --build -d --wait
if ($LASTEXITCODE -ne 0) { throw "Phase 3.1 pa rive lanse." }

& $DockerExe compose ps
& $DockerExe compose exec backend alembic current

$BaseUrl = "http://localhost:8000/api/v1"
Invoke-RestMethod "$BaseUrl/health/ready" | ConvertTo-Json -Depth 5
```

Expected migration:

```text
20260813_0004 (head)
```

## Real local Mux upload test

Choose a small MP4 file first. The following flow logs in, creates a one-time
Mux URL, uploads the file directly to Mux, then polls the protected refresh
endpoint. It never sends video bytes through FastAPI.

```powershell
$BaseUrl = "http://localhost:8000/api/v1"
$VideoFile = "C:\path\to\small-test-video.mp4"

if (-not (Test-Path $VideoFile)) { throw "Video tès la pa jwenn." }

$AdminEmail = (
    Select-String -Path .env -Pattern '^FIRST_SUPERUSER_EMAIL=(.+)$'
).Matches[0].Groups[1].Value.Trim()
$AdminPassword = (
    Select-String -Path .env -Pattern '^FIRST_SUPERUSER_PASSWORD=(.+)$'
).Matches[0].Groups[1].Value.Trim()

$LoginBody = @{
    email = $AdminEmail
    password = $AdminPassword
    device = @{
        device_id = "mux-test-windows-001"
        name = "Windows Mux Test"
        platform = "web"
    }
} | ConvertTo-Json -Depth 5

$Login = Invoke-RestMethod `
    -Uri "$BaseUrl/auth/login" `
    -Method Post `
    -ContentType "application/json" `
    -Body $LoginBody

$Headers = @{ Authorization = "Bearer $($Login.data.access_token)" }
$FileInfo = Get-Item $VideoFile

$SessionBody = @{
    file_name = $FileInfo.Name
    content_type = "video/mp4"
    file_size_bytes = $FileInfo.Length
    max_duration_seconds = 1800
    protocol = "auto"
} | ConvertTo-Json

$Upload = Invoke-RestMethod `
    -Uri "$BaseUrl/admin/video-assets/upload-sessions" `
    -Method Post `
    -Headers $Headers `
    -ContentType "application/json" `
    -Body $SessionBody

Invoke-WebRequest `
    -Uri $Upload.data.upload_url `
    -Method Put `
    -InFile $VideoFile `
    -ContentType "video/mp4"

$AssetId = $Upload.data.video_asset_id
do {
    Start-Sleep -Seconds 10
    $Status = Invoke-RestMethod `
        -Uri "$BaseUrl/admin/video-assets/$AssetId/refresh" `
        -Method Post `
        -Headers $Headers
    $Status.data.status
} while ($Status.data.status -in @("uploading", "processing"))

$Status.data | ConvertTo-Json -Depth 8

$AdminPassword = $null
$LoginBody = $null
$SessionBody = $null
```

Expected final status is `ready`, with a Mux asset ID and signed playback ID in
the Drovixa record. Delete test assets from Mux when they are no longer needed,
especially while using the free stored-asset allowance.

## Quality gates

Run backend checks inside the backend container:

```powershell
& $DockerExe compose exec backend python -m compileall -q app
& $DockerExe compose exec backend alembic heads
```

For the full development test image/environment:

```text
ruff check app tests
ruff format --check app tests
mypy app
pytest -q
```

Phase 3.1 ships with 60 passing backend tests, including Mux direct upload,
upload-to-asset correlation, signed video and thumbnail tokens, webhook
verification, invalid configuration, and out-of-order event protection.
