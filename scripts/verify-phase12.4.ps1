param([switch]$SkipClientBuild)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$GitExe = "C:\Program Files\Git\cmd\git.exe"

Set-Location $ProjectDir

$RequiredFiles = @(
    "backend\app\routes\media.py",
    "backend\migrations\versions\20260827_0013_phase12_4_admin_media.py",
    "mobile\src\i18n\index.ts"
)

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        throw "Fichye Faz 12.4 sa a pa jwenn: $File"
    }
}

$Checks = @(
    @{ Path = "admin\features\content-studio.tsx"; Pattern = 'Choose cover' },
    @{ Path = "admin\features\content-studio.tsx"; Pattern = 'advanced-studio' },
    @{ Path = "admin\app\(panel)\users\page.tsx"; Pattern = 'Add coins' },
    @{ Path = "admin\app\(panel)\users\page.tsx"; Pattern = 'Give Premium' },
    @{ Path = "backend\app\routes\admin_monetization.py"; Pattern = 'admin_grant_premium' },
    @{ Path = "backend\app\routes\admin_content.py"; Pattern = 'upload_content_media' },
    @{ Path = "mobile\app\(tabs)\index.tsx"; Pattern = 'home-poster-grid' }
)

foreach ($Check in $Checks) {
    $Text = Get-Content $Check.Path -Raw
    if ($Text -notmatch $Check.Pattern) {
        throw "Verifikasyon an pa jwenn '$($Check.Pattern)' nan $($Check.Path)."
    }
}

npm run typecheck:clients
if ($LASTEXITCODE -ne 0) {
    throw "Typecheck Faz 12.4 la echwe."
}

if (-not $SkipClientBuild) {
    npm run build:clients
    if ($LASTEXITCODE -ne 0) {
        throw "Production build Web/Admin Faz 12.4 la echwe."
    }
}

if (Test-Path $GitExe) {
    & $GitExe diff --check
    if ($LASTEXITCODE -ne 0) {
        throw "Git jwenn yon pwoblèm fòma."
    }
}

Write-Host "Faz 12.4 admin simplification and poster-grid verification pase." -ForegroundColor Green
