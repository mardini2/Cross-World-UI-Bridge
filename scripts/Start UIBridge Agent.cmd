@echo off
setlocal
cd /d "%~dp0"
set "AGENT=%CD%\UIBridge\UIBridge.exe"
if not exist "%AGENT%" (
  echo Agent not found: "%AGENT%"
  pause
  exit /b 1
)
start "" "%AGENT%"
rem Give it a moment
timeout /t 3 >nul
rem Quick health check
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5025/health').StatusCode -eq 200 } catch { $false }" | findstr /i True >nul
if errorlevel 1 (
  echo If this is the first run, a Windows Firewall prompt may be waiting behind other windows. Allow access (Private), then try again.
  pause
)
endlocal
