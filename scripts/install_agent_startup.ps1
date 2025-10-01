# scripts/install_agent_startup.ps1
# Goal: Install the UIBridge CLI package to %LOCALAPPDATA%\UIBridge
# Layout after install:
#   %LOCALAPPDATA%\UIBridge\
#     UIBridge\...   (agent onedir)
#     ui\...         (cli onedir)
#     Open UIBridge CLI.cmd
#     Start UIBridge Agent.cmd
#     install_agent_startup.ps1
#     uninstall_agent_startup.ps1
# Also create Desktop / Start Menu shortcuts and a Startup shortcut (Agent).

param(
  [string]$ZipUrl = "https://github.com/mardini2/Cross-World-UI-Bridge/releases/latest/download/UIBridge-Windows.zip"
)

$ErrorActionPreference = "Stop"

$InstallRoot = Join-Path $env:LOCALAPPDATA "UIBridge"
$ZipPath  = Join-Path $env:TEMP "UIBridge-Windows.zip"
$AgentExe = Join-Path $InstallRoot "UIBridge\UIBridge.exe"
$CliExe   = Join-Path $InstallRoot "ui\ui.exe"

Write-Host "Installing to: $InstallRoot"

if (Test-Path $InstallRoot) { Remove-Item -Recurse -Force $InstallRoot }
New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null

Write-Host "Downloading: $ZipUrl"
Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath

Write-Host "Unblocking and extracting..."
Unblock-File -Path $ZipPath
Expand-Archive -Path $ZipPath -DestinationPath $InstallRoot -Force

# If the zip unpacked into a subfolder "UIBridge-Windows", move its contents up
$Sub = Join-Path $InstallRoot "UIBridge-Windows"
if (Test-Path $Sub) {
  Get-ChildItem $Sub | Move-Item -Destination $InstallRoot -Force
  Remove-Item -Recurse -Force $Sub
}

if (-not (Test-Path $AgentExe)) { throw "Agent not found at $AgentExe" }
if (-not (Test-Path $CliExe))   { throw "CLI not found at $CliExe" }

# Create shortcuts
$Shell = New-Object -ComObject WScript.Shell
$Desktop   = [Environment]::GetFolderPath("Desktop")
$StartMenu = [Environment]::GetFolderPath("StartMenu")
$Programs  = Join-Path $StartMenu "Programs"
$Startup   = [Environment]::GetFolderPath("Startup")

function New-Shortcut($target, $lnkPath, $workdir, $desc) {
  $sc = $Shell.CreateShortcut($lnkPath)
  $sc.TargetPath = $target
  $sc.WorkingDirectory = $workdir
  $sc.IconLocation = $target
  $sc.Description = $desc
  $sc.Save()
}

# Desktop
New-Shortcut -target $AgentExe -lnkPath (Join-Path $Desktop "UIBridge Agent.lnk") -workdir (Split-Path $AgentExe) -desc "UIBridge CLI agent"
New-Shortcut -target $CliExe   -lnkPath (Join-Path $Desktop "UIBridge CLI.lnk")   -workdir (Split-Path $CliExe)   -desc "UIBridge CLI"

# Start Menu
New-Shortcut -target $AgentExe -lnkPath (Join-Path $Programs "UIBridge Agent.lnk") -workdir (Split-Path $AgentExe) -desc "UIBridge CLI agent"
New-Shortcut -target $CliExe   -lnkPath (Join-Path $Programs "UIBridge CLI.lnk")   -workdir (Split-Path $CliExe)   -desc "UIBridge CLI"

# Startup (Agent auto-start)
New-Shortcut -target $AgentExe -lnkPath (Join-Path $Startup "UIBridge Agent (auto-start).lnk") -workdir (Split-Path $AgentExe) -desc "UIBridge CLI agent (auto-start)"

Write-Host "Done. Shortcuts created. Agent will auto-start next sign-in."
