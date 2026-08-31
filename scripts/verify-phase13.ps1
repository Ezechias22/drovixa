param(
    [switch]$SkipClientBuild
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$GitExe = "C:\Program Files\Git\cmd\git.exe"

Set-Location $ProjectDir

$RootPackage = Get-Content ".\package.json" -Raw | ConvertFrom-Json
$MobilePackage = Get-Content ".\mobile\package.json" -Raw | ConvertFrom-Json
$AppConfig = Get-Content ".\mobile\app.json" -Raw | ConvertFrom-Json
$DynamicConfig = Get-Content ".\mobile\app.config.js" -Raw
$EngagementService = Get-Content ".\backend\app\services\engagement.py" -Raw
$GrowthRoutes = Get-Content ".\backend\app\routes\growth.py" -Raw
$AdminContent = Get-Content ".\backend\app\routes\admin_content.py" -Raw
$Worker = Get-Content ".\backend\app\workers\celery_app.py" -Raw

foreach ($Version in @(
    $RootPackage.version,
    $MobilePackage.version,
    $AppConfig.expo.version
)) {
    if ($Version -ne "0.13.0") {
        throw "Tout vèsyon Faz 13 yo dwe 0.13.0; youn se $Version."
    }
}

if (-not $MobilePackage.dependencies."react-native-google-mobile-ads") {
    throw "Pake natif Google Mobile Ads la pa enstale."
}

foreach ($RequiredText in @(
    "react-native-google-mobile-ads",
    "EXPO_PUBLIC_ADMOB_ANDROID_APP_ID",
    "delayAppMeasurementInit"
)) {
    if (-not $DynamicConfig.Contains($RequiredText)) {
        throw "Konfigirasyon mobil la pa gen $RequiredText."
    }
}

foreach ($RequiredText in @(
    "verify_admob_signature",
    "admob_transaction_id",
    "daily_limit",
    "with_for_update",
    "run_engagement_automations"
)) {
    if (-not $EngagementService.Contains($RequiredText)) {
        throw "Sèvis engagement lan pa gen $RequiredText."
    }
}

if (-not $GrowthRoutes.Contains("/webhooks/admob/reward")) {
    throw "Callback AdMob SSV a pa jwenn."
}

if (-not $AdminContent.Contains("queue_publication_notification")) {
    throw "Notifikasyon otomatik apre piblikasyon an pa konekte."
}

if (-not $Worker.Contains('"task": "engagement.run"')) {
    throw "Scheduler engagement lan pa konekte."
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

Write-Host "Faz 13 AdMob, coins ak engagement verification pase." -ForegroundColor Green

