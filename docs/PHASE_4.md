# Drovixa Phase 4 — User Experience

Phase 4 connects the public Next.js and Expo Router experiences to the same
FastAPI catalog. It is an additive upgrade over Phase 3.1 and keeps Mux as the
active video provider. The archive intentionally excludes every `.env` file, so
existing database, JWT and Mux credentials are preserved.

## Added backend surface

- Dynamic Home payload optimized into one request
- Discover filters and sorting
- PostgreSQL content, actor, genre and keyword search
- Search suggestions, recent history and trending terms
- Published vertical Shorts feed
- Favorites/My List
- Notifications and notification preferences
- User-aware `is_favorite` content details
- Additive Alembic head `20260814_0005`

## Windows upgrade

Run PowerShell as your normal Windows user. Do not use `docker compose down -v`.

```powershell
$ProjectRoot = "C:\Users\touss\DrovixaProject"
$ProjectDir = Join-Path $ProjectRoot "drovixa"
$ZipFile = "$env:USERPROFILE\Downloads\drovixa-phase4-experience.zip"
$DockerBin = "C:\Program Files\Docker\Docker\resources\bin"
$DockerExe = Join-Path $DockerBin "docker.exe"

$MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$DockerBin;$MachinePath;$UserPath"

Set-Location $ProjectDir

& $DockerExe compose exec -T postgres `
  pg_dump -U drovixa -d drovixa `
  --format=custom `
  --file=/tmp/drovixa-before-phase4.dump

if ($LASTEXITCODE -ne 0) { throw "Backup PostgreSQL la echwe." }

& $DockerExe compose cp `
  "postgres:/tmp/drovixa-before-phase4.dump" `
  "..\drovixa-before-phase4.dump"

if (-not (Test-Path "..\drovixa-before-phase4.dump")) {
  throw "Fichye backup la pa jwenn."
}

& $DockerExe compose down
Set-Location $ProjectRoot
Expand-Archive $ZipFile -DestinationPath . -Force
Set-Location $ProjectDir
& $DockerExe compose up --build -d --wait
& $DockerExe compose ps
& $DockerExe compose exec backend alembic current
```

The final command must display `20260814_0005 (head)`.

## Web browser

```powershell
Set-Location C:\Users\touss\DrovixaProject\drovixa
Copy-Item web\.env.example web\.env.local -Force
npm install
npm run web
```

Open `http://localhost:3000`.

## Physical Android or iPhone

Find the computer's LAN IPv4 address with `ipconfig`. The example below uses the
address already observed during development; replace it if the address changes.

Create `mobile/.env`:

```text
EXPO_PUBLIC_API_URL=http://192.168.202.130:8000/api/v1
```

Add the web origin to root `.env` when opening Next.js from another device:

```text
BACKEND_CORS_ORIGINS=["http://localhost:3000","http://localhost:3001","http://localhost:8081","http://192.168.202.130:3000"]
```

Restart the backend after changing root `.env`, then start Expo:

```powershell
Set-Location C:\Users\touss\DrovixaProject\drovixa
& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" compose up -d --force-recreate backend worker
npm run mobile
```

Install Expo Go on the phone and scan the QR code. Both devices must be on the
same network. If Windows Firewall prompts for Node.js, allow Private networks.

## Verification

```powershell
$BaseUrl = "http://localhost:8000/api/v1"
Invoke-RestMethod "$BaseUrl/health/ready" | ConvertTo-Json -Depth 5
Invoke-RestMethod "$BaseUrl/home" | ConvertTo-Json -Depth 6
Invoke-RestMethod "$BaseUrl/discover?limit=5" | ConvertTo-Json -Depth 6
Invoke-RestMethod "$BaseUrl/search/trending" | ConvertTo-Json -Depth 5
```

Local quality commands:

```powershell
docker compose exec backend pytest -q
npm run typecheck:clients
npm run build --workspace @drovixa/web
```

Mux credentials remain only in root `.env`. Never copy `MUX_TOKEN_SECRET`, the
signing private key, or the webhook secret into `web/.env.local` or `mobile/.env`.
