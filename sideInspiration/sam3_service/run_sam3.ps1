# Bring up the SAM 3 GPU sidecar with Doppler HUGGINGFACE_TOKEN (no secret print).
# Usage:
#   powershell -NoProfile -File sideInspiration/sam3_service/run_sam3.ps1

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$probe = doppler run -p ai-automation -c dev -- powershell -NoProfile -Command "if (`$env:HUGGINGFACE_TOKEN) { 'HUGGINGFACE_TOKEN=set' } else { 'HUGGINGFACE_TOKEN=missing'; exit 2 }"
if ($LASTEXITCODE -ne 0) {
  Write-Error "Doppler HUGGINGFACE_TOKEN missing in ai-automation/dev"
  exit 2
}
Write-Host $probe

doppler run -p ai-automation -c dev -- powershell -NoProfile -Command "`$env:HF_TOKEN = `$env:HUGGINGFACE_TOKEN; `$env:HUGGING_FACE_HUB_TOKEN = `$env:HUGGINGFACE_TOKEN; docker compose up --build -d; if (`$LASTEXITCODE -ne 0) { exit `$LASTEXITCODE }; docker compose ps"
