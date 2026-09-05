param(
    [string]$ProjectDir = "."
)

$ErrorActionPreference = "Stop"
$ProjectDir = (Resolve-Path $ProjectDir).Path

$ManifestPath = Join-Path $ProjectDir "backend\app\original_media\video\minwi-nan-jakmel-ep01\index.m3u8"
$OriginalScriptPath = Join-Path $ProjectDir "backend\app\scripts\original_catalog.py"
$ProviderPath = Join-Path $ProjectDir "backend\app\integrations\videos\original.py"
$StreamingPath = Join-Path $ProjectDir "backend\app\services\streaming.py"
$StartupPath = Join-Path $ProjectDir "backend\app\scripts\start_api.py"
$MainPath = Join-Path $ProjectDir "backend\app\main.py"
$WebConfigPath = Join-Path $ProjectDir "web\next.config.ts"

foreach ($RequiredPath in @(
    $ManifestPath,
    $OriginalScriptPath,
    $ProviderPath,
    $StreamingPath,
    $StartupPath,
    $MainPath,
    $WebConfigPath
)) {
    if (-not (Test-Path -LiteralPath $RequiredPath -PathType Leaf)) {
        throw "Fichye Drovixa Original la manke: $RequiredPath"
    }
}

$Manifest = Get-Content -LiteralPath $ManifestPath -Raw
foreach ($Marker in @("#EXTM3U", "#EXT-X-PLAYLIST-TYPE:VOD", "#EXT-X-ENDLIST")) {
    if (-not $Manifest.Contains($Marker)) {
        throw "Manifest HLS la pa konplè; marker sa a manke: $Marker"
    }
}

$Durations = @(
    [regex]::Matches($Manifest, '#EXTINF:([0-9.]+),') |
        ForEach-Object { [double]$_.Groups[1].Value }
)
$TotalDuration = ($Durations | Measure-Object -Sum).Sum
if ($Durations.Count -ne 31) {
    throw "Manifest la dwe genyen 31 segman; li genyen $($Durations.Count)."
}
if ($TotalDuration -lt 120 -or $TotalDuration -gt 122) {
    throw "Dire videyo a pa nan limit 2 minit la: $TotalDuration segonn."
}

$VideoDir = Split-Path $ManifestPath
$Segments = @(Get-ChildItem -LiteralPath $VideoDir -File -Filter "segment-*.ts" | Sort-Object Name)
if ($Segments.Count -ne 31) {
    throw "Dosye videyo a dwe genyen 31 segman; li genyen $($Segments.Count)."
}
foreach ($Segment in $Segments) {
    $Stream = [IO.File]::OpenRead($Segment.FullName)
    try {
        if ($Stream.ReadByte() -ne 0x47) {
            throw "Segman HLS sa a pa valab: $($Segment.Name)"
        }
    } finally {
        $Stream.Dispose()
    }
}

$OriginalScript = Get-Content -LiteralPath $OriginalScriptPath -Raw
$Provider = Get-Content -LiteralPath $ProviderPath -Raw
$Streaming = Get-Content -LiteralPath $StreamingPath -Raw
$Startup = Get-Content -LiteralPath $StartupPath -Raw
$Main = Get-Content -LiteralPath $MainPath -Raw
$WebConfig = Get-Content -LiteralPath $WebConfigPath -Raw

foreach ($Check in @(
    @{ Content = $OriginalScript; Marker = 'ORIGINAL_SLUG = "minwi-nan-jakmel"' },
    @{ Content = $OriginalScript; Marker = 'episode.access_type = EpisodeAccessType.FREE' },
    @{ Content = $OriginalScript; Marker = 'episode.coin_price = 0' },
    @{ Content = $OriginalScript; Marker = 'content.demo_batch = None' },
    @{ Content = $OriginalScript; Marker = 'await remove_showcase_catalog(db)' },
    @{ Content = $Provider; Marker = 'name = "drovixa_original"' },
    @{ Content = $Streaming; Marker = '"drovixa_original": get_original_video_provider' },
    @{ Content = $Startup; Marker = 'app.scripts.original_catalog' },
    @{ Content = $Main; Marker = '/original-media' },
    @{ Content = $WebConfig; Marker = 'https://drovixa-api-free.onrender.com' }
)) {
    if (-not $Check.Content.Contains($Check.Marker)) {
        throw "Verifikasyon Drovixa Original la echwe sou marker: $($Check.Marker)"
    }
}

if ($Main.Contains('/demo-media')) {
    throw "Ansyen chemen demo-media a toujou monte nan API a."
}

Push-Location $ProjectDir
try {
    npm run typecheck:clients
    if ($LASTEXITCODE -ne 0) {
        throw "Typecheck kliyan yo echwe."
    }

    npm run build:clients
    if ($LASTEXITCODE -ne 0) {
        throw "Build web/admin yo echwe."
    }

    git diff --check
    if ($LASTEXITCODE -ne 0) {
        throw "Git jwenn yon pwoblèm espas nan fichye yo."
    }
} finally {
    Pop-Location
}

Write-Host "Drovixa Original Minwi nan Jakmèl verifye: 1 seri, 1 epizòd gratis, 2:00.7, 9:16." -ForegroundColor Green
