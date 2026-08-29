param([switch]$SkipClientBuild)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$GitExe = "C:\Program Files\Git\cmd\git.exe"

Set-Location $ProjectDir

$RequiredFiles = @(
    "backend\migrations\versions\20260829_0014_phase12_8_viewer_experience.py",
    "backend\app\models\monetization.py",
    "backend\app\models\user.py",
    "backend\app\routes\users.py",
    "backend\app\services\streaming.py",
    "mobile\app\watch\[id].tsx",
    "mobile\app\subtitles.tsx",
    "mobile\src\features\player\DrovixaVideoPlayer.tsx",
    "mobile\src\services\offline-downloads.ts",
    "mobile\src\stores\playback-store.ts",
    "admin\features\content-studio.tsx"
)

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path -LiteralPath $File)) {
        throw "Fichye Faz 12.8 sa a pa jwenn: $File"
    }
}

$Checks = @(
    @{ Path = "backend\app\models\monetization.py"; Pattern = 'current_period_end: Mapped\[datetime\] = mapped_column\(DateTime\(timezone=True\)' },
    @{ Path = "backend\app\services\streaming.py"; Pattern = 'resume_position_seconds' },
    @{ Path = "backend\app\services\streaming.py"; Pattern = 'next_episode_id' },
    @{ Path = "backend\app\routes\users.py"; Pattern = '/me/avatar' },
    @{ Path = "mobile\src\features\player\DrovixaVideoPlayer.tsx"; Pattern = 'nativeControls' },
    @{ Path = "mobile\src\features\player\DrovixaVideoPlayer.tsx"; Pattern = 'playToEnd' },
    @{ Path = "mobile\app\watch\[id].tsx"; Pattern = 'episodeGrid' },
    @{ Path = "mobile\src\stores\playback-store.ts"; Pattern = 'lastEpisodeBySeries' },
    @{ Path = "mobile\src\services\offline-downloads.ts"; Pattern = '\.part' },
    @{ Path = "admin\features\content-studio.tsx"; Pattern = 'Publish as Short' },
    @{ Path = "admin\features\content-studio.tsx"; Pattern = 'Choose \.vtt or \.srt' },
    @{ Path = "mobile\package.json"; Pattern = 'expo-image-picker' }
)

foreach ($Check in $Checks) {
    $Text = Get-Content -LiteralPath $Check.Path -Raw
    if ($Text -notmatch $Check.Pattern) {
        throw "Verifikasyon an pa jwenn '$($Check.Pattern)' nan $($Check.Path)."
    }
}

$Phase11 = Get-ChildItem ".\admin" -Recurse -File -Include *.ts,*.tsx,*.css |
    Where-Object { $_.FullName -notmatch '[\\/](\.next|node_modules)[\\/]' } |
    Select-String -SimpleMatch "Phase 11"
if ($Phase11) {
    $Phase11
    throw "Gen yon ansyen etikèt Phase 11 ki rete nan admin an."
}

npm run typecheck:clients
if ($LASTEXITCODE -ne 0) {
    throw "Typecheck Faz 12.8 la echwe."
}

if (-not $SkipClientBuild) {
    npm run build:clients
    if ($LASTEXITCODE -ne 0) {
        throw "Production build Web/Admin Faz 12.8 la echwe."
    }
}

if (Test-Path $GitExe) {
    & $GitExe diff --check
    if ($LASTEXITCODE -ne 0) {
        throw "Git jwenn yon pwoblèm fòma."
    }
}

Write-Host "Faz 12.8 series player, subtitles, downloads, Shorts and profile verification pase." -ForegroundColor Green
