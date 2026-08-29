param(
    [ValidateSet("preview", "production")]
    [string]$Environment = "preview",
    [string]$Message = "Drovixa automatic update"
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$GitExe = "C:\Program Files\Git\cmd\git.exe"

Set-Location $ProjectDir

if (Test-Path $GitExe) {
    $Dirty = @(& $GitExe status --porcelain --untracked-files=normal)

    if ($Dirty.Count -gt 0) {
        $Dirty
        throw "Repo a gen chanjman ki poko commit. Commit/push yo anvan ou pibliye update mobil la."
    }
}

npm run typecheck --workspace @drovixa/mobile

if ($LASTEXITCODE -ne 0) {
    throw "Typecheck mobile la echwe; update la pa pibliye."
}

Push-Location ".\mobile"

try {
    npx eas-cli@latest update `
        --channel $Environment `
        --environment $Environment `
        --message $Message `
        --non-interactive

    if ($LASTEXITCODE -ne 0) {
        throw "EAS Update la echwe."
    }
} finally {
    Pop-Location
}

Write-Host "Update mobil la pibliye sou channel $Environment." -ForegroundColor Green
Write-Host "App yo ap telechaje li epi relanse otomatikman lè yo louvri oswa retounen aktif." -ForegroundColor Green
