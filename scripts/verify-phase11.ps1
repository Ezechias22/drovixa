[CmdletBinding()]
param(
    [string]$ProjectDir = "C:\Users\touss\DrovixaProject\drovixa"
)

$ErrorActionPreference = "Stop"
$DockerExe = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"

if (-not (Test-Path $DockerExe)) {
    throw "docker.exe pa jwenn. Demare Docker Desktop."
}

Set-Location $ProjectDir
& $DockerExe info | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Docker Desktop pa pare." }

& $DockerExe compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "Docker Compose configuration lan pa valid." }

$Migration = (& $DockerExe compose exec -T backend alembic current 2>&1) -join "`n"
if ($Migration -notmatch "20260825_0012") {
    throw "Migration Phase 11 lan pa sou head: $Migration"
}

$BaseUrl = "http://localhost:8000/api/v1"
$Health = Invoke-RestMethod "$BaseUrl/health/ready"
if (-not $Health.success -or $Health.data.status -ne "ready" -or $Health.data.version -ne "0.11.0") {
    throw "API Phase 11 lan pa ready."
}

$AdminEmail = (Select-String -Path ".env" -Pattern '^FIRST_SUPERUSER_EMAIL=(.*)$').Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
$AdminPassword = (Select-String -Path ".env" -Pattern '^FIRST_SUPERUSER_PASSWORD=(.*)$').Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'")
$LoginBody = @{
    email = $AdminEmail
    password = $AdminPassword
    device = @{
        device_id = "drovixa-phase11-verifier"
        name = "Phase 11 verifier"
        platform = "web"
    }
} | ConvertTo-Json -Depth 5

$Login = Invoke-RestMethod -Uri "$BaseUrl/auth/login" -Method Post -ContentType "application/json" -Body $LoginBody
$Headers = @{ Authorization = "Bearer $($Login.data.access_token)" }
$Flags = (Invoke-RestMethod -Uri "$BaseUrl/admin/feature-flags" -Headers $Headers).data

foreach ($Flag in @("ads_enabled", "daily_rewards_enabled", "referrals_enabled", "social_login_enabled", "watch_party_enabled")) {
    $Entry = $Flags | Where-Object { $_.key -eq $Flag }
    if (-not $Entry -or -not $Entry.enabled) { throw "Feature flag $Flag pa aktive." }
}

$GrowthConfig = (Invoke-RestMethod -Uri "$BaseUrl/growth/config").data
$Daily = (Invoke-RestMethod -Uri "$BaseUrl/rewards/daily" -Headers $Headers).data
$Referral = (Invoke-RestMethod -Uri "$BaseUrl/referrals/me" -Headers $Headers).data
$Summary = (Invoke-RestMethod -Uri "$BaseUrl/admin/growth/summary" -Headers $Headers).data
$Web = Invoke-WebRequest "http://localhost:3000/rewards" -UseBasicParsing
$Admin = Invoke-WebRequest "http://localhost:3001/growth" -UseBasicParsing

if ($Web.StatusCode -ne 200 -or $Admin.StatusCode -ne 200) {
    throw "Web oswa Admin Phase 11 pa reponn 200."
}

Write-Host "Phase 11 valide." -ForegroundColor Green
Write-Host "Migration: 20260825_0012 (head)" -ForegroundColor Green
Write-Host "API: 0.11.0 ready" -ForegroundColor Green
Write-Host "Daily reward: next $($Daily.next_coins) coins" -ForegroundColor Cyan
Write-Host "Referral code: prezan=$(-not [string]::IsNullOrWhiteSpace($Referral.code))" -ForegroundColor Cyan
Write-Host "Growth events: $($Summary.growth_events)" -ForegroundColor Cyan
Write-Host "Google configured: $($GrowthConfig.google_login)" -ForegroundColor Cyan
Write-Host "Apple configured: $($GrowthConfig.apple_login)" -ForegroundColor Cyan

$AdminPassword = $null
$LoginBody = $null
