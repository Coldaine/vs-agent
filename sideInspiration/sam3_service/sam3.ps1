<#
.SYNOPSIS
  Durable control script for the SAM 3 GPU sidecar (Doppler + Docker Compose).

.DESCRIPTION
  Manages sideInspiration/sam3_service without printing secrets.
  Injects Doppler ai-automation/dev HUGGINGFACE_TOKEN as HF_TOKEN for compose.

.PARAMETER Action
  up      - build (if needed) and start detached
  down    - stop and remove containers (keeps HF weight volume)
  restart - down then up
  status  - compose ps + /health if reachable
  warmup  - POST /v1/warmup (loads model into GPU)
  logs    - follow/tail container logs
  rebuild - force rebuild image then up

.EXAMPLE
  .\sam3.ps1 up
  .\sam3.ps1 warmup
  .\sam3.ps1 down
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [ValidateSet("up", "down", "restart", "status", "warmup", "logs", "rebuild")]
  [string]$Action = "status",

  [string]$DopplerProject = "ai-automation",
  [string]$DopplerConfig = "dev",
  [string]$BaseUrl = "http://127.0.0.1:8090",
  [int]$WarmupTimeoutSec = 900,
  [int]$LogTail = 80
)

$ErrorActionPreference = "Stop"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

function Assert-Cmd([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command not found: $Name"
  }
}

function Assert-HfToken {
  $probe = doppler run -p $DopplerProject -c $DopplerConfig -- powershell -NoProfile -Command `
    "if (`$env:HUGGINGFACE_TOKEN) { 'set' } else { 'missing'; exit 2 }"
  if ($LASTEXITCODE -ne 0 -or $probe -ne "set") {
    throw "Doppler $DopplerProject/$DopplerConfig missing HUGGINGFACE_TOKEN"
  }
  Write-Host "HUGGINGFACE_TOKEN=set (doppler $DopplerProject/$DopplerConfig)"
}

function Invoke-ComposeWithToken([string[]]$ComposeArgs) {
  # Map Doppler name -> HF client env for this process tree only (no print).
  # Pass compose argv through an environment variable so PowerShell never
  # reparses a joined command string.
  $env:VS_SAM3_COMPOSE_ARGS = $ComposeArgs | ConvertTo-Json -Compress
  try {
    $script = @'
$composeArgs = @($env:VS_SAM3_COMPOSE_ARGS | ConvertFrom-Json)
$env:HF_TOKEN = $env:HUGGINGFACE_TOKEN
$env:HUGGING_FACE_HUB_TOKEN = $env:HUGGINGFACE_TOKEN
$env:HUGGINGFACE_TOKEN = $env:HUGGINGFACE_TOKEN
& docker compose @composeArgs
exit $LASTEXITCODE
'@
    doppler run -p $DopplerProject -c $DopplerConfig -- powershell -NoProfile -Command $script
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  } finally {
    Remove-Item Env:VS_SAM3_COMPOSE_ARGS -ErrorAction SilentlyContinue
  }
}

function Get-Health {
  try {
    return (Invoke-RestMethod -Uri "$BaseUrl/health" -TimeoutSec 5)
  } catch {
    return $null
  }
}

Assert-Cmd docker
Assert-Cmd doppler

switch ($Action) {
  "up" {
    Assert-HfToken
    Invoke-ComposeWithToken @("up", "-d", "--build")
    docker compose ps
    $h = Get-Health
    if ($h) { Write-Host ("health: " + ($h | ConvertTo-Json -Compress)) }
    else { Write-Host "health: not ready yet (try .\sam3.ps1 status)" }
  }
  "rebuild" {
    Assert-HfToken
    Invoke-ComposeWithToken @("build", "--no-cache")
    Invoke-ComposeWithToken @("up", "-d", "--force-recreate")
    docker compose ps
  }
  "down" {
    # No HF token required to stop.
    docker compose down
    Write-Host "sam3 sidecar stopped (volume sam3-hf-cache kept)"
  }
  "restart" {
    docker compose down
    Assert-HfToken
    Invoke-ComposeWithToken @("up", "-d")
    docker compose ps
  }
  "status" {
    docker compose ps
    $h = Get-Health
    if ($null -eq $h) {
      Write-Host "health: unreachable at $BaseUrl"
      exit 1
    }
    Write-Host ("health: " + ($h | ConvertTo-Json -Compress))
    if (-not $h.ok) { exit 1 }
  }
  "warmup" {
    Write-Host "POST $BaseUrl/v1/warmup (timeout ${WarmupTimeoutSec}s)..."
    try {
      $r = Invoke-RestMethod -Method Post -Uri "$BaseUrl/v1/warmup" -TimeoutSec $WarmupTimeoutSec
      Write-Host ("warmup: " + ($r | ConvertTo-Json -Compress))
    } catch {
      Write-Error "warmup failed: $_"
      docker compose logs --tail 40
      exit 1
    }
    $h = Get-Health
    if ($h) { Write-Host ("health: " + ($h | ConvertTo-Json -Compress)) }
    if (-not $h.model_loaded) { exit 1 }
  }
  "logs" {
    docker compose logs --tail $LogTail -f
  }
}
