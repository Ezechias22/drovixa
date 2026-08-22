# Windows upgrade — Phase 9

This procedure preserves the existing `.env`, mobile `.env`, PostgreSQL volume,
Mux configuration, users, content, and administrator account.

```powershell
$ProjectRoot = "C:\Users\touss\DrovixaProject"
$ProjectDir = Join-Path $ProjectRoot "drovixa"
$ZipFile = "$env:USERPROFILE\Downloads\drovixa-phase9-notifications-render.zip"
$DockerBin = "C:\Program Files\Docker\Docker\resources\bin"
$DockerExe = Join-Path $DockerBin "docker.exe"

$MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$DockerBin;$MachinePath;$UserPath"

if (-not (Test-Path $ZipFile)) { throw "ZIP Phase 9 la pa jwenn nan Downloads." }
if (-not (Test-Path $DockerExe)) { throw "docker.exe pa jwenn." }

& $DockerExe context use desktop-linux
& $DockerExe info
if ($LASTEXITCODE -ne 0) { throw "Demare Docker Desktop anvan ou kontinye." }

Set-Location $ProjectDir
& $DockerExe compose exec -T postgres pg_dump -U drovixa -d drovixa `
    --format=custom --file=/tmp/drovixa-before-phase9.dump
if ($LASTEXITCODE -ne 0) { throw "Backup PostgreSQL la echwe." }

& $DockerExe compose cp `
    "postgres:/tmp/drovixa-before-phase9.dump" `
    "..\drovixa-before-phase9.dump"
if (-not (Test-Path "..\drovixa-before-phase9.dump")) {
    throw "Fichye backup la pa jwenn."
}

# Pa ajoute -v: volumes yo gen done ou.
& $DockerExe compose down

Set-Location $ProjectRoot
Expand-Archive -LiteralPath $ZipFile -DestinationPath $ProjectRoot -Force

Set-Location $ProjectDir
if (-not (Test-Path ".env")) { throw ".env ou a pa jwenn." }
if (-not (Test-Path "mobile\.env")) { throw "mobile\.env ou a pa jwenn." }

npm install
& $DockerExe compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "Docker Compose configuration lan pa valid." }

& $DockerExe compose up --build -d --wait --force-recreate
if ($LASTEXITCODE -ne 0) {
    & $DockerExe compose logs backend worker --tail 250
    throw "Phase 9 pa rive demare."
}

.\scripts\verify-phase9.ps1
Start-Process "http://localhost:3000"
Start-Process "http://localhost:3001/login"
Start-Process "http://localhost:8000/docs"
```

Do not run `docker compose down -v`; it deletes the database and Redis volumes.
Do not run `npm audit fix --force`; major dependency rewrites need a separate,
tested upgrade.
