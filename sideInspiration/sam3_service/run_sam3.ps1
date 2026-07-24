# Compatibility wrapper - prefer .\sam3.ps1 <up|down|status|warmup|...>
# No arguments keeps the historical startup behavior; supplied actions are forwarded.
if ($args.Count -eq 0) {
  & "$PSScriptRoot\sam3.ps1" up
} else {
  & "$PSScriptRoot\sam3.ps1" @args
}
exit $LASTEXITCODE
