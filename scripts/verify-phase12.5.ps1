param([switch]$SkipClientBuild)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$GitExe = "C:\Program Files\Git\cmd\git.exe"

Set-Location $ProjectDir

$RequiredFiles = @(
    "admin\features\content-studio.tsx",
    "backend\app\routes\admin_content.py",
    "web\components\hero.tsx",
    "web\components\section-row.tsx",
    "web\components\content-card.tsx",
    "web\features\home\HomeExperience.tsx"
)

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        throw "Fichye Faz 12.5 sa a pa jwenn: $File"
    }
}

$Checks = @(
    @{ Path = "backend\app\routes\admin_content.py"; Pattern = 'content\.poster_url = media_url' },
    @{ Path = "backend\app\routes\admin_content.py"; Pattern = 'content\.backdrop_url = media_url' },
    @{ Path = "admin\features\content-studio.tsx"; Pattern = 'Video saved as a draft episode' },
    @{ Path = "admin\features\content-studio.tsx"; Pattern = 'Cover saved\. It will still be here after a refresh' },
    @{ Path = "web\components\hero.tsx"; Pattern = 'hidden min-h-\[620px\].*md:block' },
    @{ Path = "web\components\section-row.tsx"; Pattern = 'grid grid-cols-2' },
    @{ Path = "web\components\content-card.tsx"; Pattern = 'w-full shrink-0 sm:w-\[168px\]' }
)

foreach ($Check in $Checks) {
    $Text = Get-Content $Check.Path -Raw
    if ($Text -notmatch $Check.Pattern) {
        throw "Verifikasyon an pa jwenn '$($Check.Pattern)' nan $($Check.Path)."
    }
}

npm run typecheck:clients
if ($LASTEXITCODE -ne 0) {
    throw "Typecheck Faz 12.5 la echwe."
}

if (-not $SkipClientBuild) {
    npm run build:clients
    if ($LASTEXITCODE -ne 0) {
        throw "Production build Web/Admin Faz 12.5 la echwe."
    }
}

if (Test-Path $GitExe) {
    & $GitExe diff --check
    if ($LASTEXITCODE -ne 0) {
        throw "Git jwenn yon pwoblèm fòma."
    }
}

Write-Host "Faz 12.5 cover, video draft, and mobile Web Home verification pase." -ForegroundColor Green
