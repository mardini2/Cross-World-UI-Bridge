# scripts/uninstall_agent_startup.ps1
# Goal: Remove Desktop/Start Menu/Startup shortcuts and optionally the installed agent.

param([switch]$RemoveApp)

$Desktop = [Environment]::GetFolderPath("Desktop")
$StartMenu = [Environment]::GetFolderPath("StartMenu")
$Programs = Join-Path $StartMenu "Programs"
$Startup  = [Environment]::GetFolderPath("Startup")
$LocalApp = Join-Path $env:LOCALAPPDATA "UIBridge"

$paths = @(
  (Join-Path $Desktop "UI Bridge.lnk"),
  (Join-Path $Programs "UI Bridge.lnk"),
  (Join-Path $Startup "UI Bridge (auto-start).lnk")
)

foreach ($p in $paths) { if (Test-Path $p) { Remove-Item $p -Force } }

if ($RemoveApp) {
  if (Test-Path $LocalApp) { Remove-Item $LocalApp -Recurse -Force }
  Write-Host "Removed installed app at $LocalApp"
} else {
  Write-Host "Shortcuts removed. App files kept at $LocalApp"
}
