@echo off
cd /d "%~dp0"

:: ============================================
:: MUST extract ZIP before running
:: ============================================
if not exist ".venv\Scripts\activate.bat" (
    echo ============================================
    echo   ERROR: Virtual environment not found!
    echo.
    echo   Please run setup.bat first to install.
    echo.
    echo   If you already ran setup.bat, make sure
    echo   you extracted the entire ZIP before running.
    echo ============================================
    pause
    exit /b 1
)

setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONLEGACYWINDOWSSTDIO=utf-8
set HF_ENDPOINT=https://hf-mirror.com

call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    echo Please re-run setup.bat to repair.
    pause
    exit /b 1
)

if not exist ".env" (
    if exist ".env.example" (
        echo [NOTE] Creating .env from template...
        copy /y .env.example .env >nul 2>&1
        echo.
        echo Please configure your API key in .env:
        start notepad .env
        pause
    )
)

:: 杀掉占用 8222 端口的旧进程，避免多次启动积压
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8222.*LISTENING"') do (
    echo [INFO] Port 8222 occupied by PID %%a, killing...
    taskkill /F /PID %%a >nul 2>&1
    timeout /t 1 /nobreak >nul
)

echo =========================================
echo   ThesisMind
echo.
echo   Opening: http://localhost:8222
echo   Press Ctrl+C to stop
echo =========================================
echo.

start http://localhost:8222
python src\web_server.py --port 8222

pause
