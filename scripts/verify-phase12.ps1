param(
    [switch]$SkipClientBuild,
    [string]$ApiOrigin = "",
    [string]$AppOrigin = "",
    [string]$AdminOrigin = ""
)

$ErrorActionPreference = "Stop"
$ExpectedVersion = "0.12.0"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$DockerExe = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"

Set-Location $ProjectDir

if (-not (Test-Path $DockerExe)) {
    throw "docker.exe pa jwenn. Demare oswa repare Docker Desktop."
}

$PackageFiles = @(
    "package.json",
    "mobile\package.json",
    "web\package.json",
    "admin\package.json"
)

foreach ($PackageFile in $PackageFiles) {
    $Package = Get-Content $PackageFile -Raw | ConvertFrom-Json
    if ($Package.version -ne $ExpectedVersion) {
        throw "$PackageFile gen version $($Package.version), men nou bezwen $ExpectedVersion."
    }
}

$AppConfig = Get-Content "mobile\app.json" -Raw | ConvertFrom-Json
if ($AppConfig.expo.version -ne $ExpectedVersion -or $AppConfig.expo.extra.phase -ne 12) {
    throw "Mobile app.json pa sou Faz 12 / version $ExpectedVersion."
}

$BackendVersion = Get-Content "backend\app\core\version.py" -Raw
if ($BackendVersion -notmatch 'APP_VERSION\s*=\s*"0\.12\.0"') {
    throw "Backend APP_VERSION pa sou 0.12.0."
}

$ForbiddenTracked = @(
    git ls-files -- `
        ".env" `
        "mobile/.env" `
        "mobile/google-services.json" `
        "GoogleService-Info.plist" `
        "*firebase*service-account*.json" `
        "*.jks" `
        "*.keystore" `
        "*.p8" `
        "*.p12"
) | Where-Object { $_ }

if ($ForbiddenTracked) {
    $ForbiddenTracked
    throw "Git ap swiv omwen yon fichye sekrè oswa signing credential."
}

& $DockerExe compose config --quiet
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose configuration lan pa valid."
}

npm run typecheck:clients
if ($LASTEXITCODE -ne 0) {
    throw "Client TypeScript verification lan echwe."
}

if (-not $SkipClientBuild) {
    npm run build:clients
    if ($LASTEXITCODE -ne 0) {
        throw "Web/Admin production build lan echwe."
    }
}

if ($ApiOrigin -or $AppOrigin -or $AdminOrigin) {
    if (-not ($ApiOrigin -and $AppOrigin -and $AdminOrigin)) {
        throw "Bay ApiOrigin, AppOrigin ak AdminOrigin ansanm."
    }
    & "$ProjectDir\ops\smoke\production-smoke.ps1" `
        -ApiOrigin $ApiOrigin `
        -AppOrigin $AppOrigin `
        -AdminOrigin $AdminOrigin `
        -ExpectedVersion $ExpectedVersion
}

Write-Host "Faz 12 release verification pase." -ForegroundColor Green
