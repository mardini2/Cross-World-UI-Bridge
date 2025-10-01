# scripts/uninstall_agent_startup.ps1
# Remove Desktop/Start Menu/Startup shortcuts and the installed package (optional).

param([switch]$RemoveApp)

$Desktop   = [Environment]::GetFolderPath("Desktop")
$StartMenu = [Environment]::GetFolderPath("StartMenu")
$Programs  = Join-Path $StartMenu "Programs"
$Startup   = [Environment]::GetFolderPath("Startup")
$InstallRoot = Join-Path $env:LOCALAPPDATA "UIBridge"

$paths = @(
  (Join-Path $Desktop "UIBridge Agent.lnk"),
  (Join-Path $Desktop "UIBridge CLI.lnk"),
  (Join-Path $Programs "UIBridge Agent.lnk"),
  (Join-Path $Programs "UIBridge CLI.lnk"),
  (Join-Path $Startup  "UIBridge Agent (auto-start).lnk")
)

foreach ($p in $paths) { if (Test-Path $p) { Remove-Item $p -Force } }

if ($RemoveApp) {
  if (Test-Path $InstallRoot) { Remove-Item $InstallRoot -Recurse -Force }
  Write-Host "Removed installed app at $InstallRoot"
} else {
  Write-Host "Shortcuts removed. App files kept at $InstallRoot"
}
