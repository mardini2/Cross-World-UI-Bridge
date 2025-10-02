@echo off
setlocal
cd /d "%~dp0ui"
start "" cmd /k ui.exe --help
endlocal
