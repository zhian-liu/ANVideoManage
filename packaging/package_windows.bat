@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0package_windows.ps1" %*
if errorlevel 1 (
    echo Packaging failed.
    pause
    exit /b 1
)
echo Packaging completed.
pause
