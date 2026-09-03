@echo off
taskkill /FI "WINDOWTITLE eq VideoManage ZLMediaKit*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq VideoManage Backend*" /T /F >nul 2>&1
echo VideoManage processes stopped.
