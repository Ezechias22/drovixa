param([switch]$SkipClientBuild)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$GitExe = "C:\Program Files\Git\cmd\git.exe"

Set-Location $ProjectDir

$RequiredFiles = @(
    "mobile\app\language.tsx",
    "mobile\app\playback-settings.tsx",
    "mobile\app\security.tsx",
    "mobile\app\help.tsx",
    "mobile\assets\notification-icon.png",
    "mobile\src\i18n\index.ts",
    "mobile\src\stores\playback-store.ts"
)

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        throw "Fichye Faz 12.3 sa a pa jwenn: $File"
    }
}

$Checks = @(
    @{ Path = "backend\app\integrations\videos\mux.py"; Pattern = 'static_renditions' },
    @{ Path = "backend\app\routes\auth.py"; Pattern = 'change-password' },
    @{ Path = "mobile\app.json"; Pattern = 'notification-icon.png' },
    @{ Path = "mobile\src\services\offline-downloads.ts"; Pattern = 'DOWNLOAD_PREPARING' },
    @{ Path = "mobile\src\features\player\DrovixaVideoPlayer.tsx"; Pattern = 'replaceAsync' },
    @{ Path = "admin\features\content-studio.tsx"; Pattern = 'Quick publish' }
)

foreach ($Check in $Checks) {
    $Text = Get-Content $Check.Path -Raw
    if ($Text -notmatch $Check.Pattern) {
        throw "Verifikasyon an pa jwenn '$($Check.Pattern)' nan $($Check.Path)."
    }
}

npm run typecheck:clients
if ($LASTEXITCODE -ne 0) {
    throw "Typecheck Faz 12.3 la echwe."
}

if (-not $SkipClientBuild) {
    npm run build:clients
    if ($LASTEXITCODE -ne 0) {
        throw "Production build Web/Admin Faz 12.3 la echwe."
    }
}

if (Test-Path $GitExe) {
    & $GitExe diff --check
    if ($LASTEXITCODE -ne 0) {
        throw "Git jwenn yon pwoblèm fòma."
    }
}

Write-Host "Faz 12.3 functional repair verification pase." -ForegroundColor Green
