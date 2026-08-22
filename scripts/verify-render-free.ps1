param(
    [Parameter(Mandatory = $true)]
    [string]$ApiUrl,

    [Parameter(Mandatory = $true)]
    [string]$WebUrl,

    [Parameter(Mandatory = $true)]
    [string]$AdminUrl
)

$ErrorActionPreference = "Stop"

function Normalize-BaseUrl {
    param([string]$Value)
    return $Value.Trim().TrimEnd("/")
}

$ApiUrl = Normalize-BaseUrl $ApiUrl
$WebUrl = Normalize-BaseUrl $WebUrl
$AdminUrl = Normalize-BaseUrl $AdminUrl

Write-Host "Teste API Render gratis la..." -ForegroundColor Cyan
$Health = Invoke-RestMethod `
    -Uri "$ApiUrl/api/v1/health/ready" `
    -TimeoutSec 120

if (-not $Health.success -or $Health.data.status -ne "ready") {
    throw "API a reponn men li pa ready."
}

Write-Host "API ready; database ak Redis reponn." -ForegroundColor Green

$Web = Invoke-WebRequest -Uri $WebUrl -TimeoutSec 120
if ($Web.StatusCode -ne 200) {
    throw "Web la pa reponn 200."
}
Write-Host "Web la reponn 200." -ForegroundColor Green

$Admin = Invoke-WebRequest -Uri "$AdminUrl/login" -TimeoutSec 120
if ($Admin.StatusCode -ne 200) {
    throw "Admin login lan pa reponn 200."
}
Write-Host "Admin login lan reponn 200." -ForegroundColor Green

Write-Host ""
Write-Host "Drovixa Render Free pare pou tès." -ForegroundColor Green
Write-Host "API   : $ApiUrl/api/v1" -ForegroundColor Cyan
Write-Host "Web   : $WebUrl" -ForegroundColor Cyan
Write-Host "Admin : $AdminUrl/login" -ForegroundColor Cyan
