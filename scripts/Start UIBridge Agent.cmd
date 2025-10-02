@echo off
setlocal
cd /d "%~dp0"

set "AGENT=%CD%\UIBridge\UIBridge.exe"
if not exist "%AGENT%" (
  echo [x] Agent not found: "%AGENT%"
  pause
  exit /b 1
)

rem Start the agent
start "" "%AGENT%"

rem Give it a moment to bind the port
timeout /t 2 >nul

rem Quick health check without token
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$u='http://127.0.0.1:5025/health';" ^
  "try { (Invoke-WebRequest -UseBasicParsing $u -TimeoutSec 2).StatusCode -eq 200 } catch { $false }" | findstr /i True >nul

if errorlevel 1 (
  echo.
  echo If this is the first run, a Windows Firewall prompt may be waiting behind other windows.
  echo Allow access [Private], then try again.
  echo.
  echo Debug helper:
  echo   powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start-UIBridge-Debug.ps1"
  echo.
  pause
) else (
  echo Agent is running on http://127.0.0.1:5025
  timeout /t 1 >nul
)
endlocal
