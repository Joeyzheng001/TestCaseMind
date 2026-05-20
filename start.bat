@echo off
cd /d "%~dp0"
setlocal

:: Force UTF-8 for Python I/O on Windows
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONLEGACYWINDOWSSTDIO=utf-8

echo =========================================
echo   ThesisMind 论文辅助工作台
echo =========================================
echo.
echo   当前目录: %cd%
echo.

:: Activate virtual environment
if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Please run setup.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

:: Check .env config
if not exist ".env" (
    if exist ".env.example" (
        echo [NOTE] .env not found, creating from .env.example...
        copy /y .env.example .env >nul 2>&1
        echo Please edit .env to add your API Key:
        echo   notepad .env
        start notepad .env
        pause
    )
)

echo Starting ThesisMind...
echo.
echo   Web interface: http://localhost:8222
echo.
echo   Press Ctrl+C to stop the server.
echo.

python src\web_server.py --port 8222

pause
