[CmdletBinding()]
param(
    [string]$ProjectDir = "C:\Users\touss\DrovixaProject\drovixa"
)

$ErrorActionPreference = "Stop"
$DockerBin = "C:\Program Files\Docker\Docker\resources\bin"
$DockerExe = Join-Path $DockerBin "docker.exe"

if (-not (Test-Path $DockerExe)) {
    throw "docker.exe pa jwenn."
}

$MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$DockerBin;$MachinePath;$UserPath"
Set-Location $ProjectDir

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
if ($Migration -notmatch "20260823_0010") {
    throw "Migration Phase 9 lan pa sou head: $Migration"
}

$BaseUrl = "http://localhost:8000/api/v1"
$Health = Invoke-RestMethod "$BaseUrl/health/ready"
if (-not $Health.success -or $Health.data.status -ne "ready") {
    throw "API a pa ready."
}

$PushConfig = (Invoke-RestMethod "$BaseUrl/push/config").data

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
        device_id = "drovixa-phase9-verifier"
        name = "Phase 9 verifier"
        platform = "web"
    }
} | ConvertTo-Json -Depth 5

$Login = Invoke-RestMethod `
    -Uri "$BaseUrl/auth/login" `
    -Method Post `
    -ContentType "application/json" `
    -Body $LoginBody

$Headers = @{ Authorization = "Bearer $($Login.data.access_token)" }
$Provider = (Invoke-RestMethod `
    -Uri "$BaseUrl/admin/notifications/provider-status" `
    -Headers $Headers
).data

$Web = Invoke-WebRequest "http://localhost:3000" -UseBasicParsing
$Admin = Invoke-WebRequest "http://localhost:3001/login" -UseBasicParsing
if ($Web.StatusCode -ne 200 -or $Admin.StatusCode -ne 200) {
    throw "Web oswa Admin pa reponn 200."
}

Write-Host "Phase 9 valide." -ForegroundColor Green
Write-Host "Migration: 20260823_0010 (head)" -ForegroundColor Green
Write-Host "API: ready" -ForegroundColor Green
Write-Host "Admin: $($Login.data.user.email) [$($Login.data.user.roles -join ', ')]" -ForegroundColor Green
Write-Host "Push provider: $($Provider.provider); configured=$($Provider.configured)" -ForegroundColor Cyan

if (-not $PushConfig.enabled) {
    Write-Warning "Firebase poko aktive. In-app notifications ap mache, men remote push pap voye."
}

$AdminPassword = $null
$LoginBody = $null
