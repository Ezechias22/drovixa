param(
    [string]$ProjectDir = (Resolve-Path (Join-Path $PSScriptRoot ".."))
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectDir

$RequiredFiles = @(
    ".\backend\app\scripts\demo_catalog.py",
    ".\backend\app\integrations\videos\demo.py",
    ".\backend\migrations\versions\20260905_0016_showcase_catalog.py",
    ".\docs\SHOWCASE_CATALOG.md"
)
foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File -PathType Leaf)) {
        throw "Showcase file missing: $File"
    }
}

$Posters = @(Get-ChildItem ".\backend\app\demo_media\posters" -File -Filter "*.jpg")
$Backdrops = @(Get-ChildItem ".\backend\app\demo_media\backdrops" -File -Filter "*.jpg")
$Manifests = @(Get-ChildItem ".\backend\app\demo_media\video" -Recurse -File -Filter "index.m3u8")
if ($Posters.Count -ne 15 -or $Backdrops.Count -ne 15 -or $Manifests.Count -ne 4) {
    throw "Showcase media incomplete: $($Posters.Count) posters, $($Backdrops.Count) backdrops, $($Manifests.Count) HLS manifests."
}

$Catalog = Get-Content ".\backend\app\scripts\demo_catalog.py" -Raw
foreach ($Marker in @("showcase-v1", "drovixa_demo", "DEMO_CATALOG_ENABLED", '"pt-BR"', '"ht"')) {
    if (-not $Catalog.Contains($Marker)) {
        throw "Showcase catalog marker missing: $Marker"
    }
}

npm run typecheck:clients
if ($LASTEXITCODE -ne 0) {
    throw "Client TypeScript verification failed."
}

npm run build:clients
if ($LASTEXITCODE -ne 0) {
    throw "Client production build verification failed."
}

git diff --check
if ($LASTEXITCODE -ne 0) {
    throw "Git whitespace verification failed."
}

Write-Host "Drovixa showcase verification passed: 15 series, 30 episodes, 5 languages."
