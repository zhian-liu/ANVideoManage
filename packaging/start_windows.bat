@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "ZLM=%ROOT%zlm"
set "BACKEND_EXE=%BACKEND%\VideoManageBackend.exe"
set "PYTHON_EXE=%BACKEND%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%BACKEND%\venv\Scripts\python.exe"

if not exist "%BACKEND%\.env" if exist "%BACKEND%\.env.example" (
    copy /Y "%BACKEND%\.env.example" "%BACKEND%\.env" >nul
)

if not exist "%BACKEND_EXE%" if not exist "%PYTHON_EXE%" (
    where py >nul 2>&1
    if errorlevel 1 (
        echo Python 3.11+ was not found. Install Python and run this file again.
        pause
        exit /b 1
    )
    echo Creating backend virtual environment...
    py -3.11 -m venv "%BACKEND%\.venv"
    if errorlevel 1 (
        echo Failed to create the backend virtual environment.
        pause
        exit /b 1
    )
    set "PYTHON_EXE=%BACKEND%\.venv\Scripts\python.exe"
    echo Installing backend dependencies...
    "%PYTHON_EXE%" -m pip install -r "%BACKEND%\requirements.txt"
    if errorlevel 1 (
        echo Failed to install backend dependencies.
        pause
        exit /b 1
    )
)

if not exist "%ZLM%\MediaServer.exe" (
    echo ZLMediaKit runtime is missing from the zlm folder.
    pause
    exit /b 1
)

start "VideoManage ZLMediaKit" /D "%ZLM%" "%ZLM%\MediaServer.exe" -c "%ZLM%\config.ini"
if exist "%BACKEND_EXE%" (
    start "VideoManage Backend" /D "%BACKEND%" "%BACKEND_EXE%"
) else (
    start "VideoManage Backend" /D "%BACKEND%" "%PYTHON_EXE%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
)

timeout /t 3 /nobreak >nul
start "" http://127.0.0.1:8000
echo VideoManage started at http://127.0.0.1:8000
