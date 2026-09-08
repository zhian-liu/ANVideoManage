@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart_dev.ps1"
if errorlevel 1 (
    echo.
    echo Development services failed to restart. See the error above.
    pause
    exit /b 1
)
