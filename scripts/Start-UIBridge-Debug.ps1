# Requires: Windows PowerShell 5+ (built-in). No admin needed.
# Goal: Start the agent, then prove whether port 5025 is listening and show the latest agent log.

$ErrorActionPreference = "Stop"

function Test-Health {
  param([string]$Url = "http://127.0.0.1:5025/health")
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri $Url
    return ($resp.StatusCode -eq 200)
  } catch {
    return $false
  }
}

Write-Host "=== UIBridge Debug ===" -ForegroundColor Cyan
$root = (Get-Location).Path
$agent = Join-Path $root "UIBridge\UIBridge.exe"

Write-Host ("Root:  {0}" -f $root)
Write-Host ("Agent: {0}  Exists: {1}" -f $agent, (Test-Path $agent))

if (-not (Test-Path $agent)) {
  Write-Host "[x] Agent EXE not found; check your unzip location." -ForegroundColor Red
  exit 1
}

# Start
$proc = Start-Process -FilePath $agent -PassThru
Start-Sleep -Seconds 2
Write-Host ("Started PID {0}" -f $proc.Id)

# Port listening?
$listen = (Get-NetTCPConnection -LocalPort 5025 -State Listen -ErrorAction SilentlyContinue)
if ($null -eq $listen) {
  Write-Host "Port 5025 is NOT listening yet."
} else {
  Write-Host "Port 5025 is listening."
}

# Health
if (Test-Health) {
  Write-Host "[/health] OK (200)"
} else {
  Write-Host "[x] /health check failed (timeout or 401)"
}

# Logs
$localApp = [Environment]::GetFolderPath('LocalApplicationData')
$logDir = Join-Path $localApp "UIBridge\logs"
Write-Host ("Log dir: {0}" -f $logDir)

if (Test-Path $logDir) {
  $latest = Get-ChildItem $logDir -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($latest) {
    Write-Host ("Latest log: {0}" -f $latest.FullName)
    try {
      Get-Content -Path $latest.FullName -Tail 30
    } catch {
      Write-Host "[!] Failed to read log." -ForegroundColor Yellow
    }
  } else {
    Write-Host "No log files yet." -ForegroundColor Yellow
  }
} else {
  Write-Host "Log directory not found." -ForegroundColor Yellow
}

Write-Host "=== End Debug ===" -ForegroundColor Cyan
