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
:: Find Python 3.9-3.14
:: ============================================
set "PYTHON="
set "PYVER="

:: Step 1: Check PATH
for %%p in (python3 python) do (
    where %%p >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%v in ('%%p -c "import sys; print(sys.version_info.major)" 2^>nul') do set "MAJ=%%v"
        for /f "tokens=*" %%w in ('%%p -c "import sys; print(sys.version_info.minor)" 2^>nul') do set "MIN=%%w"
        if "!MAJ!"=="3" if !MIN! GEQ 9 if !MIN! LEQ 14 (
            set "PYTHON=%%p"
            set "PYVER=!MAJ!.!MIN!"
        )
    )
    if defined PYTHON goto :found
)

:: Step 2: Check common install dirs
set "CHECK="
for %%d in (
    C:\Python314 C:\Python313 C:\Python312 C:\Python311 C:\Python310 C:\Python39
) do (
    if exist "%%d\python.exe" (
        set "CHECK=%%d\python.exe"
        goto :check_ver
    )
)

:: Step 3: Check LocalAppData
if defined LocalAppData (
    for %%d in (Python314 Python313 Python312 Python311 Python310 Python39) do (
        if exist "%LocalAppData%\Programs\Python\%%d\python.exe" (
            set "CHECK=%LocalAppData%\Programs\Python\%%d\python.exe"
            goto :check_ver
        )
    )
)

:: Step 4: Check ProgramFiles
for %%d in (Python314 Python313 Python312 Python311 Python310 Python39) do (
    if exist "%ProgramFiles%\%%d\python.exe" (
        set "CHECK=%ProgramFiles%\%%d\python.exe"
        goto :check_ver
    )
)
goto :nopython

:check_ver
for /f "tokens=*" %%v in ('"!CHECK!" -c "import sys; print(sys.version_info.major)" 2^>nul') do set "MAJ=%%v"
for /f "tokens=*" %%w in ('"!CHECK!" -c "import sys; print(sys.version_info.minor)" 2^>nul') do set "MIN=%%w"
if "!MAJ!"=="3" if !MIN! GEQ 9 if !MIN! LEQ 14 (
    set "PYTHON=!CHECK!"
    set "PYVER=!MAJ!.!MIN!"
    goto :found
)

:nopython
echo [ERROR] Python 3.9-3.14 not found.
echo.
echo Please install Python 3.9-3.14:
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
set PIP_DISABLE_PIP_VERSION_CHECK=1
set PIP_DEFAULT_TIMEOUT=60
set "PIP_COMMON=--disable-pip-version-check --retries 5 --timeout 60 --prefer-binary"
set "PIP_TUNA=-i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn"
set "PIP_ALI=-i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com"
set "PIP_USTC=-i https://pypi.mirrors.ustc.edu.cn/simple --trusted-host pypi.mirrors.ustc.edu.cn"
set "PIP_PYPI=-i https://pypi.org/simple --trusted-host pypi.org --trusted-host files.pythonhosted.org"
set "PIP_LOCAL_LINKS="

if exist "wheels\*.whl" (
    set "PIP_LOCAL_LINKS=!PIP_LOCAL_LINKS! --find-links=wheels"
)

if exist "*.whl" (
    set "PIP_LOCAL_LINKS=!PIP_LOCAL_LINKS! --find-links=."
)

if defined PIP_LOCAL_LINKS (
    echo   Local wheel files detected.
    python -m pip install --upgrade pip setuptools wheel %PIP_COMMON% !PIP_LOCAL_LINKS! --no-index
    if !errorlevel! neq 0 (
        echo   [WARN] Could not upgrade pip from local wheels, continuing...
    )
) else (
    python -m pip install --upgrade pip setuptools wheel %PIP_COMMON% %PIP_TUNA%
    if !errorlevel! neq 0 (
        echo   [WARN] Could not upgrade pip from Tsinghua mirror, continuing...
    )
)

echo Installing dependencies...
set "OK=0"

:: Try local wheels first. If the wheel set is incomplete, switch to mirrors while
:: still preferring local files for packages that are available locally.
if defined PIP_LOCAL_LINKS (
    echo   Trying local wheels first...
    python -m pip install -r requirements.txt %PIP_COMMON% !PIP_LOCAL_LINKS! --no-index
    if !errorlevel! equ 0 (
        set "OK=1"
        echo   [OK] Installed from local wheels
    ) else (
        echo.
        echo   ---- Local wheel install incomplete ^(see above^), switching to mirrors... ----
        echo.
    )
)

:: Network install: prefer China mirrors because direct PyPI often fails behind
:: regional firewalls, antivirus HTTPS inspection, or corporate proxies.
if "!OK!"=="0" (
    echo   Downloading from Tsinghua mirror ^(this may take a few minutes^)...
    python -m pip install -r requirements.txt %PIP_COMMON% !PIP_LOCAL_LINKS! %PIP_TUNA%
    if !errorlevel! equ 0 (
        set "OK=1"
        echo   [OK] Installed from Tsinghua mirror
    )
)

if "!OK!"=="0" (
    echo   Tsinghua mirror unreachable, trying Aliyun mirror...
    python -m pip install -r requirements.txt %PIP_COMMON% !PIP_LOCAL_LINKS! %PIP_ALI%
    if !errorlevel! equ 0 (
        set "OK=1"
        echo   [OK] Installed from Aliyun mirror
    )
)

if "!OK!"=="0" (
    echo   Aliyun mirror unreachable, trying USTC mirror...
    python -m pip install -r requirements.txt %PIP_COMMON% !PIP_LOCAL_LINKS! %PIP_USTC%
    if !errorlevel! equ 0 (
        set "OK=1"
        echo   [OK] Installed from USTC mirror
    )
)

if "!OK!"=="0" (
    echo   China mirrors unreachable, trying default PyPI...
    python -m pip install -r requirements.txt %PIP_COMMON% !PIP_LOCAL_LINKS! %PIP_PYPI%
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
    echo   This is usually a network/proxy/SSL problem, not a code problem.
    echo   Common causes:
    echo   1. Firewall, VPN, antivirus, or corporate proxy blocks pip HTTPS
    echo   2. Network cannot reach PyPI or the selected mirror
    echo   3. Proxy is required but HTTP_PROXY/HTTPS_PROXY is not configured
    echo.
    echo   Manual fix 1 - open cmd in this folder:
    echo   .venv\Scripts\activate
    echo   python -m pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com
    echo.
    echo   Manual fix 2 - if you use a proxy:
    echo   set HTTPS_PROXY=http://127.0.0.1:7890
    echo   set HTTP_PROXY=http://127.0.0.1:7890
    echo   python -m pip install -r requirements.txt -i https://pypi.org/simple
    echo ============================================
    pause
    exit /b 1
)
echo [OK] Dependencies installed

:: ============================================
:: Pre-download embedding model (uses mirror for China users)
:: ============================================
echo.
echo Pre-downloading embedding model BAAI/bge-small-zh-v1.5 ...
set HF_ENDPOINT=https://hf-mirror.com
python -c "import os; os.environ.setdefault('HF_ENDPOINT','https://hf-mirror.com'); from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5'); print('Model ready')" 2>&1
if !errorlevel! neq 0 (
    echo [NOTE] Could not pre-download model. First startup will try again.
)

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
:: Done — Start server
:: ============================================
echo.
echo =========================================
echo   Setup complete! Starting server...
echo.
echo   Open: http://localhost:8222
echo   Press Ctrl+C to stop
echo =========================================
echo.

start http://localhost:8222
python src\web_server.py --port 8222

pause
