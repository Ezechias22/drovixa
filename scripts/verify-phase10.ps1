[CmdletBinding()]
param(
    [string]$ProjectDir = "C:\Users\touss\DrovixaProject\drovixa"
)

$ErrorActionPreference = "Stop"
$DockerBin = "C:\Program Files\Docker\Docker\resources\bin"
$DockerExe = Join-Path $DockerBin "docker.exe"

if (-not (Test-Path $DockerExe)) {
    throw "docker.exe pa jwenn. Demare Docker Desktop."
}

$MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$DockerBin;$MachinePath;$UserPath"
Set-Location $ProjectDir

& $DockerExe info | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop pa pare." }

& $DockerExe compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "Docker Compose configuration lan pa valid." }

$Services = & $DockerExe compose ps --format json | ConvertFrom-Json
$Unhealthy = @($Services | Where-Object {
    $_.State -ne "running" -or ($_.Health -and $_.Health -ne "healthy")
})
if ($Unhealthy.Count -gt 0) {
    $Unhealthy | Format-Table Name, State, Health
    throw "Gen sèvis ki pa pare."
}

$Migration = (& $DockerExe compose exec -T backend alembic current 2>&1) -join "`n"
if ($Migration -notmatch "20260824_0011") {
    throw "Migration Phase 10 lan pa sou head: $Migration"
}

$BaseUrl = "http://localhost:8000/api/v1"
$Health = Invoke-RestMethod "$BaseUrl/health/ready"
if (
    -not $Health.success -or
    $Health.data.status -ne "ready" -or
    $Health.data.version -ne "0.10.0"
) {
    throw "API Phase 10 lan pa ready."
}

$AdminEmail = (
    Select-String -Path ".env" -Pattern '^FIRST_SUPERUSER_EMAIL=(.*)$'
).Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
$AdminPassword = (
    Select-String -Path ".env" -Pattern '^FIRST_SUPERUSER_PASSWORD=(.*)$'
).Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")

$LoginBody = @{
    email = $AdminEmail
    password = $AdminPassword
    device = @{
        device_id = "drovixa-phase10-verifier"
        name = "Phase 10 verifier"
        platform = "web"
    }
} | ConvertTo-Json -Depth 5

$Login = Invoke-RestMethod `
    -Uri "$BaseUrl/auth/login" `
    -Method Post `
    -ContentType "application/json" `
    -Body $LoginBody

$Headers = @{ Authorization = "Bearer $($Login.data.access_token)" }
$Profiles = (Invoke-RestMethod -Uri "$BaseUrl/profiles" -Headers $Headers).data
$Experience = (
    Invoke-RestMethod -Uri "$BaseUrl/admin/experience/summary" -Headers $Headers
).data
$Flags = (Invoke-RestMethod -Uri "$BaseUrl/admin/feature-flags" -Headers $Headers).data

$RequiredFlags = @(
    "multi_profile_enabled",
    "kids_mode_enabled",
    "ratings_enabled",
    "downloads_enabled",
    "chromecast_enabled",
    "airplay_enabled"
)

foreach ($Flag in $RequiredFlags) {
    $Entry = $Flags | Where-Object { $_.key -eq $Flag }
    if (-not $Entry -or -not $Entry.enabled) {
        throw "Feature flag $Flag pa aktive."
    }
}

$Web = Invoke-WebRequest "http://localhost:3000/profiles" -UseBasicParsing
$Admin = Invoke-WebRequest "http://localhost:3001/experience" -UseBasicParsing
if ($Web.StatusCode -ne 200 -or $Admin.StatusCode -ne 200) {
    throw "Web oswa Admin Phase 10 pa reponn 200."
}

Write-Host "Phase 10 valide." -ForegroundColor Green
Write-Host "Migration: 20260824_0011 (head)" -ForegroundColor Green
Write-Host "API: 0.10.0 ready" -ForegroundColor Green
Write-Host "Profiles: $($Profiles.Count)" -ForegroundColor Cyan
Write-Host "Ratings: $($Experience.ratings)" -ForegroundColor Cyan
Write-Host "Feature flags Phase 10: aktive" -ForegroundColor Green

$AdminPassword = $null
$LoginBody = $null
