<#
Goal: Install a simple 'ui' command in the user's PATH that launches this bundle's ui.exe.
Why: So users can open any new terminal and just type 'ui'.
What it does:
- Creates %LOCALAPPDATA%\UIBridgeCLI\bin
- Writes ui.cmd that shells out to the bundled ui.exe
- Adds that folder to the *user* PATH if it's not already there
Notes:
- No admin required; PATH change applies to NEW terminals after running.
- Safe to run multiple times (idempotent).
#>

$ErrorActionPreference = 'Stop'

# resolve ui.exe path relative to this script
$root  = Split-Path -Parent $MyInvocation.MyCommand.Path     # ...\scripts
$base  = Split-Path -Parent $root                             # extracted zip root
$uiExe = Join-Path $base 'ui\ui.exe'

if (-not (Test-Path -LiteralPath $uiExe)) {
  Write-Error "CLI not found at: $uiExe`nMake sure you're running from the extracted bundle."
}

# destination shim directory under user profile
$binDir = Join-Path $env:LOCALAPPDATA 'UIBridgeCLI\bin'
New-Item -ItemType Directory -Force -Path $binDir | Out-Null

# write a tiny cmd shim that forwards all args to ui.exe
$shimPath = Join-Path $binDir 'ui.cmd'
$shimBody = "@echo off`r`n""$uiExe"" %*`r`n"
[System.IO.File]::WriteAllText($shimPath, $shimBody, New-Object System.Text.UTF8Encoding($false))

# ensure the binDir is in the *user* PATH (case-insensitive match)
$currentUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$parts = @()
if ($currentUserPath) { $parts = $currentUserPath -split ';' }

$alreadyPresent = $false
foreach ($p in $parts) {
  if ($p -and ($p.Trim()) -ieq $binDir) { $alreadyPresent = $true; break }
}

if (-not $alreadyPresent) {
  $newPath = if ($currentUserPath) { "$currentUserPath;$binDir" } else { $binDir }
  [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
  Write-Host "Added '$binDir' to your USER PATH."
  Write-Host "Open a NEW terminal window to use the 'ui' command."
} else {
  Write-Host "PATH already contains '$binDir'."
}

Write-Host "Installed CLI shim at: $shimPath"
Write-Host "Try: ui --help"
