param(
    [Parameter(Mandatory = $true)][string]$ApiOrigin,
    [Parameter(Mandatory = $true)][string]$AppOrigin,
    [Parameter(Mandatory = $true)][string]$AdminOrigin
)

$ErrorActionPreference = "Stop"
$ApiOrigin = $ApiOrigin.TrimEnd("/")
$AppOrigin = $AppOrigin.TrimEnd("/")
$AdminOrigin = $AdminOrigin.TrimEnd("/")

Invoke-RestMethod "$ApiOrigin/api/v1/health/ready" | Out-Null
Invoke-RestMethod "$ApiOrigin/api/v1/genres" | Out-Null
Invoke-WebRequest "$AppOrigin/" -UseBasicParsing | Out-Null
Invoke-WebRequest "$AdminOrigin/login" -UseBasicParsing | Out-Null

Write-Host "Drovixa smoke tests passed." -ForegroundColor Green
