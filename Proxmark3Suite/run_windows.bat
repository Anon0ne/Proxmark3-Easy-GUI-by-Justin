@echo off
cd /d "%~dp0"
if exist "dist\Proxmark3Suite.exe" (
    start "" "dist\Proxmark3Suite.exe"
) else if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "app.py"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1"
)
