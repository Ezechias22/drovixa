param(
    [switch]$SkipClientBuild
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$GitExe = "C:\Program Files\Git\cmd\git.exe"

Set-Location $ProjectDir

$AppConfig = Get-Content ".\mobile\app.json" -Raw | ConvertFrom-Json
$EasConfig = Get-Content ".\mobile\eas.json" -Raw | ConvertFrom-Json
$Updater = Get-Content ".\mobile\src\components\AutomaticAppUpdater.tsx" -Raw
$Layout = Get-Content ".\mobile\app\_layout.tsx" -Raw
$Publisher = Get-Content ".\scripts\publish-mobile-ota.ps1" -Raw

if ($AppConfig.expo.updates.checkAutomatically -ne "ON_LOAD") {
    throw "Expo Updates pa configured pou tcheke otomatikman lè app la louvri."
}

if ($AppConfig.expo.runtimeVersion.policy -ne "appVersion") {
    throw "runtimeVersion la dwe sèvi ak policy appVersion."
}

if ($EasConfig.build.preview.channel -ne "preview") {
    throw "Pwofil preview la pa sou channel preview."
}

if ($EasConfig.build.production.channel -ne "production") {
    throw "Pwofil production lan pa sou channel production."
}

foreach ($RequiredCall in @(
    "checkForUpdateAsync",
    "fetchUpdateAsync",
    "reloadAsync"
)) {
    if (-not $Updater.Contains($RequiredCall)) {
        throw "AutomaticAppUpdater pa gen $RequiredCall."
    }
}

if (-not $Layout.Contains("<AutomaticAppUpdater />")) {
    throw "Root layout la pa monte AutomaticAppUpdater."
}

if (
    -not $Publisher.Contains("eas-cli@latest update") -or
    -not $Publisher.Contains("--channel `$Environment") -or
    -not $Publisher.Contains("--environment `$Environment")
) {
    throw "Script pibliye OTA a pa configured kòrèkteman."
}

npm run typecheck:clients

if ($LASTEXITCODE -ne 0) {
    throw "Typecheck clients yo echwe."
}

if (-not $SkipClientBuild) {
    npm run build:clients

    if ($LASTEXITCODE -ne 0) {
        throw "Build Web/Admin yo echwe."
    }
}

if (Test-Path $GitExe) {
    & $GitExe diff --check

    if ($LASTEXITCODE -ne 0) {
        throw "Git jwenn yon pwoblèm fòma."
    }
}

Write-Host "Faz 12.9 automatic mobile update verification pase." -ForegroundColor Green
