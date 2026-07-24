# Compatibility wrapper — prefer .\sam3.ps1 <up|down|status|warmup|...>
# Usage: powershell -NoProfile -File sideInspiration/sam3_service/run_sam3.ps1
& "$PSScriptRoot\sam3.ps1" up @args
