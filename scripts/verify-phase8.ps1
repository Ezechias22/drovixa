$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
$DockerBin = "C:\Program Files\Docker\Docker\resources\bin"
$DockerExe = Join-Path $DockerBin "docker.exe"

if (-not (Test-Path $DockerExe)) {
    throw "docker.exe pa jwenn. Louvri oswa repare Docker Desktop."
}

$MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$DockerBin;$MachinePath;$UserPath"

Set-Location $ProjectDir
& $DockerExe compose config --quiet
& $DockerExe compose ps

$Migration = & $DockerExe compose exec -T backend alembic current
if ($Migration -notmatch "20260822_0009") {
    throw "Migration Phase 8 la pa aktive. Rezilta: $Migration"
}

$Health = Invoke-RestMethod "http://localhost:8000/api/v1/health/ready"
if (-not $Health.success -or $Health.data.status -ne "ready") {
    throw "Backend lan pa ready."
}

$Web = Invoke-WebRequest "http://localhost:3000" -UseBasicParsing
$Admin = Invoke-WebRequest "http://localhost:3001/login" -UseBasicParsing
if ($Web.StatusCode -ne 200 -or $Admin.StatusCode -ne 200) {
    throw "Web oswa Admin lan pa reponn 200."
}

Write-Host "Phase 8 verifye: migration, API, Web ak Admin yo pare." -ForegroundColor Green
