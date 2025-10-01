# scripts/install_agent_startup.ps1
# Goal: Install the UIBridge agent EXE to %LOCALAPPDATA%\UIBridge, create Desktop & Start Menu shortcuts,
# and add a Startup shortcut so the agent launches on sign-in.

param(
  [string]$ZipUrl = "https://github.com/mardini2/Cross-World-UI-Bridge/releases/latest/download/UIBridge-Windows.zip"
)

$ErrorActionPreference = "Stop"

$LocalApp = Join-Path $env:LOCALAPPDATA "UIBridge"
$BinDir   = $LocalApp
$ZipPath  = Join-Path $env:TEMP "UIBridge-Windows.zip"
$ExePath  = Join-Path $BinDir   "UIBridge.exe"

Write-Host "Installing to: $BinDir"

if (-not (Test-Path $BinDir)) { New-Item -ItemType Directory -Force -Path $BinDir | Out-Null }

# Download latest build
Write-Host "Downloading latest build..."
Invoke-WebRequest -Uri $ZipUrl -OutFile $ZipPath

# Unblock and extract
Write-Host "Unblocking and extracting..."
Unblock-File -Path $ZipPath
Expand-Archive -Path $ZipPath -DestinationPath $BinDir -Force

if (-not (Test-Path $ExePath)) {
  throw "UIBridge.exe not found after extraction."
}

# Create Desktop and Start Menu shortcuts
$Shell = New-Object -ComObject WScript.Shell

$Desktop = [Environment]::GetFolderPath("Desktop")
$StartMenu = [Environment]::GetFolderPath("StartMenu")
$Programs = Join-Path $StartMenu "Programs"
$Startup  = [Environment]::GetFolderPath("Startup")

$DesktopLnk = Join-Path $Desktop "UI Bridge.lnk"
$ProgramsLnk = Join-Path $Programs "UI Bridge.lnk"
$StartupLnk = Join-Path $Startup "UI Bridge (auto-start).lnk"

function New-Shortcut($target, $lnkPath, $workdir) {
  $sc = $Shell.CreateShortcut($lnkPath)
  $sc.TargetPath = $target
  $sc.WorkingDirectory = $workdir
  $sc.IconLocation = $target
  $sc.Description = "Cross-World UI Bridge agent"
  $sc.Save()
}

Write-Host "Creating shortcuts..."
New-Shortcut -target $ExePath -lnkPath $DesktopLnk -workdir $BinDir
New-Shortcut -target $ExePath -lnkPath $ProgramsLnk -workdir $BinDir
New-Shortcut -target $ExePath -lnkPath $StartupLnk -workdir $BinDir

Write-Host "Done. The agent will start on your next sign-in. You can also launch it from the Desktop shortcut."
