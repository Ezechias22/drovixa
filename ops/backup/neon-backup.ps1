param(
    [string]$DatabaseUrl = $env:DATABASE_BACKUP_URL,
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$DockerExe = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"

if ([string]::IsNullOrWhiteSpace($DatabaseUrl) -or $DatabaseUrl -notmatch '^postgres(ql)?://') {
    throw "Set DATABASE_BACKUP_URL to the direct Neon PostgreSQL URL."
}

if (-not (Test-Path $DockerExe)) {
    throw "docker.exe pa jwenn. Demare Docker Desktop."
}

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) "backups"
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path $OutputDirectory).Path
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$FileName = "drovixa-$Stamp.dump"
$OutputFile = Join-Path $OutputDirectory $FileName
$ShellCommand = 'pg_dump --dbname="$DATABASE_URL" --format=custom --compress=9 --no-owner --no-privileges --file="/backup/{0}" && pg_restore --list "/backup/{0}" >/dev/null' -f $FileName

& $DockerExe run --rm `
    --env "DATABASE_URL=$DatabaseUrl" `
    --volume "${OutputDirectory}:/backup" `
    postgres:17-alpine `
    sh -lc $ShellCommand

if ($LASTEXITCODE -ne 0) {
    throw "Backup or pg_restore validation failed."
}

if (-not (Test-Path $OutputFile) -or (Get-Item $OutputFile).Length -lt 1024) {
    throw "Backup output is missing or too small."
}

$Hash = (Get-FileHash $OutputFile -Algorithm SHA256).Hash.ToLowerInvariant()
"$Hash  $FileName" | Set-Content "$OutputFile.sha256" -Encoding ascii

Write-Host "Neon backup created and validated: $OutputFile" -ForegroundColor Green
Write-Host "The database URL was not printed or written to the backup." -ForegroundColor Cyan
