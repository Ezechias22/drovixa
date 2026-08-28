param([switch]$SkipClientBuild)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$GitExe = "C:\Program Files\Git\cmd\git.exe"

Set-Location $ProjectDir

$RequiredFiles = @(
    "backend\app\models\monetization.py",
    "backend\tests\test_admin_operations.py"
)

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        throw "Fichye Faz 12.7 sa a pa jwenn: $File"
    }
}

$Checks = @(
    @{ Path = "backend\app\models\monetization.py"; Pattern = 'starts_at: Mapped\[datetime\] = mapped_column\(DateTime\(timezone=True\)\)' },
    @{ Path = "backend\app\models\monetization.py"; Pattern = 'current_period_start: Mapped\[datetime\] = mapped_column\(DateTime\(timezone=True\)\)' },
    @{ Path = "backend\app\models\monetization.py"; Pattern = 'current_period_end: Mapped\[datetime\] = mapped_column\(DateTime\(timezone=True\)' },
    @{ Path = "backend\tests\test_admin_operations.py"; Pattern = 'test_subscription_period_columns_are_timezone_aware' }
)

foreach ($Check in $Checks) {
    $Text = Get-Content $Check.Path -Raw
    if ($Text -notmatch $Check.Pattern) {
        throw "Verifikasyon an pa jwenn '$($Check.Pattern)' nan $($Check.Path)."
    }
}

npm run typecheck:clients
if ($LASTEXITCODE -ne 0) {
    throw "Typecheck Faz 12.7 la echwe."
}

if (-not $SkipClientBuild) {
    npm run build:clients
    if ($LASTEXITCODE -ne 0) {
        throw "Production build Web/Admin Faz 12.7 la echwe."
    }
}

if (Test-Path $GitExe) {
    & $GitExe diff --check
    if ($LASTEXITCODE -ne 0) {
        throw "Git jwenn yon pwoblèm fòma."
    }
}

Write-Host "Faz 12.7 PostgreSQL subscription timezone verification pase." -ForegroundColor Green
