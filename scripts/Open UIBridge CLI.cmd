@echo off
setlocal
cd /d "%~dp0ui"
if exist ui.exe (
  start "" cmd /k ui.exe --help
) else (
  echo [ERROR] ui.exe not found in "%CD%"
  pause
)
endlocal
