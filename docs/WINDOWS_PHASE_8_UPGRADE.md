# Windows upgrade from Drovixa Phase 7 to Phase 8

Start Docker Desktop first. Run the commands from a normal PowerShell session;
only firewall changes, if later needed for phone testing, require Administrator.

The Phase 8 archive intentionally excludes `.env` and `mobile/.env`. Never use
`docker compose down -v` during an upgrade.

```powershell
$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\touss\DrovixaProject"
$ProjectDir = Join-Path $ProjectRoot "drovixa"
$ZipFile = "$env:USERPROFILE\Downloads\drovixa-phase8-production.zip"
$DockerBin = "C:\Program Files\Docker\Docker\resources\bin"
$DockerExe = Join-Path $DockerBin "docker.exe"

$MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$DockerBin;$MachinePath;$UserPath"
$env:COMPOSE_PARALLEL_LIMIT = "2"

if (-not (Test-Path $ZipFile)) { throw "ZIP Phase 8 la pa jwenn nan Downloads." }
if (-not (Test-Path "$ProjectDir\.env")) { throw ".env aktyèl la pa jwenn." }

& $DockerExe context use desktop-linux
& $DockerExe info | Out-Null
Set-Location $ProjectDir

$BackupName = "drovixa-before-phase8-$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')).dump"
& $DockerExe compose exec -T postgres pg_dump -U drovixa -d drovixa --format=custom --file="/tmp/$BackupName"
if ($LASTEXITCODE -ne 0) { throw "Backup PostgreSQL la echwe. Pa kontinye." }

$BackupPath = Join-Path $ProjectRoot $BackupName
& $DockerExe compose cp "postgres:/tmp/$BackupName" $BackupPath
if (-not (Test-Path $BackupPath)) { throw "Fichye backup la pa jwenn." }

& $DockerExe compose down
Set-Location $ProjectRoot
Expand-Archive -LiteralPath $ZipFile -DestinationPath $ProjectRoot -Force
Set-Location $ProjectDir

if (-not (Test-Path ".env")) { throw ".env ou a pa prezève. Pa demare sèvis yo." }

npm install
& $DockerExe compose config --quiet
& $DockerExe compose up --build -d --wait --force-recreate
if ($LASTEXITCODE -ne 0) {
    & $DockerExe compose logs backend --tail 200
    throw "Phase 8 pa rive demare."
}

& $DockerExe compose exec backend python -m app.scripts.bootstrap_superuser
& $DockerExe compose exec backend alembic current
& "$ProjectDir\scripts\verify-phase8.ps1"
```

The fixed bootstrap command creates the email currently stored in
`FIRST_SUPERUSER_EMAIL` if it does not exist, or resets that account to the
password currently stored in `FIRST_SUPERUSER_PASSWORD` if it does exist.
