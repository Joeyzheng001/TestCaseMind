@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

:: Force UTF-8 for Python I/O on Windows (PEP 540 + PYTHONIOENCODING fallback)
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONLEGACYWINDOWSSTDIO=utf-8

echo =========================================
echo   ThesisMind 论文辅助工作台 - 安装向导
echo =========================================
echo.

:: ── Python detection with version check (need 3.9+) ──
set "PYTHON="
set "PYVER="
for %%p in (python3 python) do (
    where %%p >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%v in ('%%p -c "import sys; print(sys.version_info.major)"') do set "PYMAJOR=%%v"
        for /f "tokens=*" %%w in ('%%p -c "import sys; print(sys.version_info.minor)"') do set "PYMINOR=%%w"
        if "!PYMAJOR!"=="3" (
            if !PYMINOR! GEQ 9 (
                set "PYTHON=%%p"
                set "PYVER=!PYMAJOR!.!PYMINOR!"
            )
        )
    )
    if defined PYTHON goto :python_found
)
:python_found

if "%PYTHON%"=="" (
    echo [ERROR] Python 3.9+ not found.
    echo.
    echo Please install Python 3.9 or newer:
    echo   https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
echo [OK] Python %PYVER% (%PYTHON%)

:: ── Virtual environment ──
if not exist ".venv" (
    echo Creating virtual environment...
    "%PYTHON%" -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        echo Make sure Python's "venv" module is installed.
        pause
        exit /b 1
    )
)
call .venv\Scripts\activate.bat
if !errorlevel! neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)
echo [OK] Virtual environment activated

:: ── Upgrade pip ──
echo Upgrading pip...
python -m pip install --upgrade pip -q 2>nul

:: ── Install dependencies ──
echo Installing dependencies...
set "INSTALL_OK=0"

:: Priority 1: offline wheels (bundled in release zip)
if exist "wheels\" (
    for %%f in (wheels\*.whl) do set "HAS_WHEELS=1"
    if defined HAS_WHEELS (
        echo   [1/3] Trying offline wheels...
        python -m pip install --no-index --find-links=wheels -r requirements.txt -q 2>nul
        if !errorlevel! equ 0 set "INSTALL_OK=1"
    )
)

:: Priority 2: Tsinghua mirror (faster for China users)
if "!INSTALL_OK!"=="0" (
    echo   [2/3] Trying Tsinghua mirror...
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q 2>nul
    if !errorlevel! equ 0 set "INSTALL_OK=1"
)

:: Priority 3: default PyPI
if "!INSTALL_OK!"=="0" (
    echo   [3/3] Trying default PyPI...
    python -m pip install -r requirements.txt -q 2>nul
    if !errorlevel! equ 0 set "INSTALL_OK=1"
)

if "!INSTALL_OK!"=="0" (
    echo [ERROR] All installation sources failed.
    echo Please check your network connection and try again.
    pause
    exit /b 1
)
echo [OK] Dependencies installed

:: ── Knowledge base check ──
echo.
if exist "knowledge_base\vector_store.sqlite3" (
    echo [OK] Knowledge base vector index ready
) else (
    echo [NOTE] Vector index not found - citation search may be limited
)

:: ── Config file .env ──
if not exist ".env" (
    if exist ".env.example" (
        copy /y .env.example .env >nul 2>&1
        echo [OK] Config file .env created
        echo    Please edit .env to add your API Key before starting:
        echo    notepad .env
    ) else (
        echo [WARN] .env.example not found
    )
)

:: ── Chinese font check ──
echo.
if exist "C:\Windows\Fonts\simsun.ttc" (
    echo [OK] Chinese font: SimSun found
) else if exist "C:\Windows\Fonts\msyh.ttc" (
    echo [OK] Chinese font: Microsoft YaHei found
) else (
    echo [NOTE] Standard Chinese fonts not found, PDF export may need manual font setup
)

:: ── Finish ──
echo.
echo =========================================
echo   Setup complete!
echo.
echo   Quick start:
echo     Double-click start.bat
echo.
echo   Or manually:
echo     .venv\Scripts\activate
echo     python src\web_server.py --port 8222
echo.
echo   Then open: http://localhost:8222
echo   First time: Visit License page to start free trial
echo.
echo =========================================
echo   Press any key to exit...
pause >nul
