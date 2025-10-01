# scripts/install_cli_shim.ps1
# Goal: install a 'ui' shim into %LOCALAPPDATA%\UIBridge\bin and add it to PATH (user).
$Bin = Join-Path $env:LOCALAPPDATA "UIBridge\bin"
if (-not (Test-Path $Bin)) { New-Item -ItemType Directory -Force -Path $Bin | Out-Null }

$Cmd = @'
@echo off
REM ui.cmd - call Typer CLI entry
py -3 -m app.cli.cli %*
'@
$Cmd | Out-File -Encoding ascii (Join-Path $Bin "ui.cmd")

# Add to PATH (user scope)
$cur = [Environment]::GetEnvironmentVariable("Path","User")
if ($cur -notlike "*$Bin*") {
  [Environment]::SetEnvironmentVariable("Path", "$cur;$Bin", "User")
  Write-Host "Added $Bin to your user PATH. Open a new terminal to use 'ui'."
} else {
  Write-Host "'ui' already in PATH."
}
