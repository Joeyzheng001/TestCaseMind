@echo off
cd /d "%~dp0"

:: ============================================
:: MUST extract ZIP before running
:: ============================================
if not exist "requirements.txt" (
    echo ============================================
    echo   ERROR: ThesisMind files not found!
    echo.
    echo   Please EXTRACT the entire ZIP file first,
    echo   then run setup.bat from the extracted folder.
    echo.
    echo   Do NOT double-click from inside the ZIP!
    echo ============================================
    pause
    exit /b 1
)

setlocal EnableDelayedExpansion

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set PYTHONLEGACYWINDOWSSTDIO=utf-8

echo =========================================
echo   ThesisMind - Setup Wizard
echo =========================================
echo.
echo   Working dir: %cd%
echo.

:: ============================================
:: Find Python 3.9+
:: ============================================
set "PYTHON="
set "PYVER="

:: Step 1: Check PATH
for %%p in (python3 python) do (
    where %%p >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%v in ('%%p -c "import sys; print(sys.version_info.major)" 2^>nul') do set "MAJ=%%v"
        for /f "tokens=*" %%w in ('%%p -c "import sys; print(sys.version_info.minor)" 2^>nul') do set "MIN=%%w"
        if "!MAJ!"=="3" if !MIN! GEQ 9 (
            set "PYTHON=%%p"
            set "PYVER=!MAJ!.!MIN!"
        )
    )
    if defined PYTHON goto :found
)

:: Step 2: Check common install dirs
set "CHECK="
for %%d in (
    C:\Python313 C:\Python312 C:\Python311 C:\Python310 C:\Python39
) do (
    if exist "%%d\python.exe" (
        set "CHECK=%%d\python.exe"
        goto :check_ver
    )
)

:: Step 3: Check LocalAppData
if defined LocalAppData (
    for %%d in (Python313 Python312 Python311 Python310 Python39) do (
        if exist "%LocalAppData%\Programs\Python\%%d\python.exe" (
            set "CHECK=%LocalAppData%\Programs\Python\%%d\python.exe"
            goto :check_ver
        )
    )
)

:: Step 4: Check ProgramFiles
for %%d in (Python313 Python312 Python311) do (
    if exist "%ProgramFiles%\%%d\python.exe" (
        set "CHECK=%ProgramFiles%\%%d\python.exe"
        goto :check_ver
    )
)
goto :nopython

:check_ver
for /f "tokens=*" %%v in ('"!CHECK!" -c "import sys; print(sys.version_info.major)" 2^>nul') do set "MAJ=%%v"
for /f "tokens=*" %%w in ('"!CHECK!" -c "import sys; print(sys.version_info.minor)" 2^>nul') do set "MIN=%%w"
if "!MAJ!"=="3" if !MIN! GEQ 9 (
    set "PYTHON=!CHECK!"
    set "PYVER=!MAJ!.!MIN!"
    goto :found
)

:nopython
echo [ERROR] Python 3.9+ not found.
echo.
echo Please install Python 3.9 or newer:
echo   https://www.python.org/downloads/
echo.
echo IMPORTANT: Check "Add Python to PATH" when installing.
echo.
echo If already installed, run this file and report the error.
pause
exit /b 1

:found
echo [OK] Python %PYVER% found
echo      %PYTHON%
echo.

:: ============================================
:: Create virtual environment
:: ============================================
if not exist ".venv" (
    echo Creating virtual environment...
    "%PYTHON%" -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create .venv
        echo Make sure Python "venv" module is available.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment exists
)

call .venv\Scripts\activate.bat
if !errorlevel! neq 0 (
    echo [ERROR] Cannot activate .venv
    pause
    exit /b 1
)

:: ============================================
:: Install dependencies
:: ============================================
echo.
echo Upgrading pip...
python -m pip install --upgrade pip -q 2>nul

echo Installing dependencies...
set "OK=0"

:: 尝试离线 wheels（错误输出可见，方便排查；失败则自动切换网络安装）
if exist "wheels\*.whl" (
    echo   Trying offline wheels...
    python -m pip install --no-index --find-links=wheels -r requirements.txt
    if !errorlevel! equ 0 (
        set "OK=1"
        echo   [OK] Installed from offline wheels
    ) else (
        echo.
        echo   ---- Offline install failed ^(see above^), switching to network... ----
        echo.
    )
)

:: 网络安装：优先清华镜像，失败则 PyPI
if "!OK!"=="0" (
    echo   Downloading from network ^(this may take a few minutes^)...
    python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if !errorlevel! equ 0 (
        set "OK=1"
        echo   [OK] Installed from Tsinghua mirror
    )
)

if "!OK!"=="0" (
    echo   Tsinghua mirror unreachable, trying default PyPI...
    python -m pip install -r requirements.txt
    if !errorlevel! equ 0 (
        set "OK=1"
        echo   [OK] Installed from PyPI
    )
)

if "!OK!"=="0" (
    echo.
    echo ============================================
    echo   [ERROR] Dependency install failed.
    echo.
    echo   Possible causes:
    echo   1. No internet or firewall blocks pip
    echo   2. Corporate proxy not configured
    echo.
    echo   Manual fix - open cmd in this folder:
    echo   .venv\Scripts\activate
    echo   pip install -r requirements.txt
    echo ============================================
    pause
    exit /b 1
)
echo [OK] Dependencies installed

:: ============================================
:: Checks
:: ============================================
echo.
if exist "knowledge_base\vector_store.sqlite3" (
    echo [OK] Vector index ready
) else (
    echo [NOTE] Vector index not found - some features limited
)

if not exist ".env" (
    if exist ".env.example" (
        copy /y .env.example .env >nul 2>&1
        echo [OK] Created .env - please edit to add your API key
    )
)

:: ============================================
:: Done
:: ============================================
echo.
echo =========================================
echo   Setup complete!
echo.
echo   Start the server:
echo     Double-click start.bat
echo.
echo   Or manually:
echo     .venv\Scripts\activate
echo     python src\web_server.py --port 8222
echo.
echo   Then open: http://localhost:8222
echo =========================================
echo.
echo   Press any key to exit...
pause >nul
