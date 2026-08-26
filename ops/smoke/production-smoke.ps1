param(
    [Parameter(Mandatory = $true)][string]$ApiOrigin,
    [Parameter(Mandatory = $true)][string]$AppOrigin,
    [Parameter(Mandatory = $true)][string]$AdminOrigin,
    [string]$ExpectedVersion = "0.12.0",
    [int]$Attempts = 8
)

$ErrorActionPreference = "Stop"
$ApiOrigin = $ApiOrigin.TrimEnd("/")
$AppOrigin = $AppOrigin.TrimEnd("/")
$AdminOrigin = $AdminOrigin.TrimEnd("/")

foreach ($Origin in @($ApiOrigin, $AppOrigin, $AdminOrigin)) {
    if (-not $Origin.StartsWith("https://")) {
        throw "Production smoke tests require HTTPS origins: $Origin"
    }
}

function Invoke-WithRetry {
    param([scriptblock]$Action, [string]$Label)

    for ($Attempt = 1; $Attempt -le $Attempts; $Attempt++) {
        try {
            return & $Action
        } catch {
            if ($Attempt -eq $Attempts) {
                throw "$Label failed after $Attempts attempts: $($_.Exception.Message)"
            }
            Start-Sleep -Seconds ([Math]::Min(5 * $Attempt, 30))
        }
    }
}

$Live = Invoke-WithRetry {
    Invoke-RestMethod "$ApiOrigin/api/v1/health/live" -TimeoutSec 30
} "API liveness"

$Ready = Invoke-WithRetry {
    Invoke-RestMethod "$ApiOrigin/api/v1/health/ready" -TimeoutSec 30
} "API readiness"

if ($Live.data.version -ne $ExpectedVersion -or $Ready.data.version -ne $ExpectedVersion) {
    throw "API version mismatch. Expected $ExpectedVersion."
}

if ($Ready.data.status -ne "ready" -or $Ready.data.checks.database -ne "up") {
    throw "API dependencies are not ready."
}

$Web = Invoke-WithRetry {
    Invoke-WebRequest "$AppOrigin/" -UseBasicParsing -TimeoutSec 30
} "Public Web"

$Admin = Invoke-WithRetry {
    Invoke-WebRequest "$AdminOrigin/login" -UseBasicParsing -TimeoutSec 30
} "Admin Web"

foreach ($Response in @($Web, $Admin)) {
    if ($Response.StatusCode -ne 200) {
        throw "A Web surface returned HTTP $($Response.StatusCode)."
    }
    if (-not $Response.Headers["Content-Security-Policy"]) {
        throw "A Web surface is missing Content-Security-Policy."
    }
    if ($Response.Headers["X-Content-Type-Options"] -ne "nosniff") {
        throw "A Web surface is missing X-Content-Type-Options=nosniff."
    }
}

Write-Host "Production smoke tests passed for Drovixa $ExpectedVersion." -ForegroundColor Green
