param([switch]$SkipClientBuild)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$GitExe = "C:\Program Files\Git\cmd\git.exe"

Set-Location $ProjectDir

$RequiredFiles = @(
    "admin\app\(panel)\users\page.tsx",
    "backend\app\routes\admin_monetization.py",
    "backend\app\schemas\monetization.py",
    "backend\tests\test_admin_operations.py"
)

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        throw "Fichye Faz 12.6 sa a pa jwenn: $File"
    }
}

$Checks = @(
    @{ Path = "backend\app\routes\admin_monetization.py"; Pattern = 'ADMIN_PREMIUM_PLAN_SLUG' },
    @{ Path = "backend\app\routes\admin_monetization.py"; Pattern = 'current_end\.tzinfo is None' },
    @{ Path = "backend\app\routes\admin_monetization.py"; Pattern = 'replace\(tzinfo=UTC\)' },
    @{ Path = "backend\app\schemas\monetization.py"; Pattern = 'days: int = Field\(default=30, ge=1, le=36500\)' },
    @{ Path = "admin\app\(panel)\users\page.tsx"; Pattern = 'Duration in days' },
    @{ Path = "admin\app\(panel)\users\page.tsx"; Pattern = '1 to 36,500 days' },
    @{ Path = "backend\tests\test_admin_operations.py"; Pattern = '"days": 4000' }
)

foreach ($Check in $Checks) {
    $Text = Get-Content $Check.Path -Raw
    if ($Text -notmatch $Check.Pattern) {
        throw "Verifikasyon an pa jwenn '$($Check.Pattern)' nan $($Check.Path)."
    }
}

npm run typecheck:clients
if ($LASTEXITCODE -ne 0) {
    throw "Typecheck Faz 12.6 la echwe."
}

if (-not $SkipClientBuild) {
    npm run build:clients
    if ($LASTEXITCODE -ne 0) {
        throw "Production build Web/Admin Faz 12.6 la echwe."
    }
}

if (Test-Path $GitExe) {
    & $GitExe diff --check
    if ($LASTEXITCODE -ne 0) {
        throw "Git jwenn yon pwoblèm fòma."
    }
}

Write-Host "Faz 12.6 Premium duration and timezone hotfix verification pase." -ForegroundColor Green
